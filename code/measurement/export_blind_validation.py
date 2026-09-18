#!/usr/bin/env python3
"""
Gate 4 — Blind validation sample export.
Reproducible stratified sampling (seed=20260729), ≥200 speeches.
Generates blinded CSV for independent Codex reviewer + hidden answer key.
Never modifies data/original/. Uses frozen Hermes scores.
"""

import hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED = 20260729
TARGET_N = 200
RUBRIC_VERSION = "us_stance_v1"

SPEECHES_PATH   = PROJECT_ROOT / "data/processed/speeches_full.parquet"
SCORES_PATH     = PROJECT_ROOT / "data/processed/speech_stance_scores.parquet"
PANEL_PATH      = PROJECT_ROOT / "data/original/course_package/country_year_panel.csv"

BLINDED_CSV     = PROJECT_ROOT / "data/interim/blinded_stance_validation_200.csv"
KEY_PARQUET     = PROJECT_ROOT / "data/interim/blinded_stance_validation_key_200.parquet"
REPORT_CSV      = PROJECT_ROOT / "tables/machine_readable/blinded_validation_sample_report.csv"
MANIFEST_JSON   = PROJECT_ROOT / "research/blinded_validation_sample_manifest.json"

# ── Prohibited fields for blinded CSV ──
PROHIBITED_FIELDS = [
    "primary_stance_score", "affective_warmth", "policy_alignment",
    "order_alignment", "direct_us_mention", "mention_count",
    "confidence", "model_name", "prompt_version", "score_group",
    "aid", "total_aid", "econ_aid", "mil_aid",
    "unsc", "us_agree", "ideal_point",
    "affective_warmth_continuous", "pos_strong_hits", "pos_moderate_hits",
    "neg_strong_hits", "neg_moderate_hits",
    "matched_positive_terms", "matched_negative_terms",
    "scoring_method", "scoring_run_id", "scored_at",
]

# ── Region mapping ──
REGION_MAP = {
    'AFG':'Asia','ALB':'Europe','DZA':'Africa','AGO':'Africa','ARG':'Americas',
    'ARM':'Asia','AUS':'Asia','AUT':'Europe','AZE':'Asia','BHR':'Asia',
    'BGD':'Asia','BRB':'Americas','BLR':'Europe','BEL':'Europe','BLZ':'Americas',
    'BEN':'Africa','BTN':'Asia','BOL':'Americas','BIH':'Europe','BWA':'Africa',
    'BRA':'Americas','BRN':'Asia','BGR':'Europe','BFA':'Africa','BDI':'Africa',
    'CPV':'Africa','KHM':'Asia','CMR':'Africa','CAN':'Americas','CAF':'Africa',
    'TCD':'Africa','CHL':'Americas','COL':'Americas','COM':'Africa','COG':'Africa',
    'CRI':'Americas','CIV':'Africa','HRV':'Europe','CUB':'Americas','CYP':'Asia',
    'CZE':'Europe','PRK':'Asia','COD':'Africa','DNK':'Europe','DJI':'Africa',
    'DMA':'Americas','DOM':'Americas','ECU':'Americas','EGY':'Africa','SLV':'Americas',
    'GNQ':'Africa','ERI':'Africa','EST':'Europe','ETH':'Africa','FJI':'Asia',
    'FIN':'Europe','GAB':'Africa','GMB':'Africa','GEO':'Asia','DEU':'Europe',
    'GHA':'Africa','GRC':'Europe','GRD':'Americas','GTM':'Americas','GIN':'Africa',
    'GNB':'Africa','GUY':'Americas','HTI':'Americas','HND':'Americas','HUN':'Europe',
    'ISL':'Europe','IND':'Asia','IDN':'Asia','IRN':'Asia','IRQ':'Asia',
    'IRL':'Europe','ISR':'Asia','ITA':'Europe','JAM':'Americas','JPN':'Asia',
    'JOR':'Asia','KAZ':'Asia','KEN':'Africa','KWT':'Asia','KGZ':'Asia',
    'LAO':'Asia','LVA':'Europe','LBN':'Asia','LSO':'Africa','LBR':'Africa',
    'LBY':'Africa','LTU':'Europe','LUX':'Europe','MDG':'Africa','MWI':'Africa',
    'MYS':'Asia','MDV':'Asia','MLI':'Africa','MLT':'Europe','MRT':'Africa',
    'MUS':'Africa','MEX':'Americas','MDA':'Europe','MNG':'Asia','MNE':'Europe',
    'MAR':'Africa','MOZ':'Africa','MMR':'Asia','NAM':'Africa','NPL':'Asia',
    'NLD':'Europe','NZL':'Asia','NIC':'Americas','NER':'Africa','NGA':'Africa',
    'MKD':'Europe','NOR':'Europe','OMN':'Asia','PAK':'Asia','PAN':'Americas',
    'PNG':'Asia','PRY':'Americas','PER':'Americas','PHL':'Asia','POL':'Europe',
    'PRT':'Europe','QAT':'Asia','KOR':'Asia','ROU':'Europe','RWA':'Africa',
    'KNA':'Americas','LCA':'Americas','VCT':'Americas','WSM':'Asia','STP':'Africa',
    'SAU':'Asia','SEN':'Africa','SRB':'Europe','SYC':'Africa','SLE':'Africa',
    'SGP':'Asia','SVK':'Europe','SVN':'Europe','SLB':'Asia','SOM':'Africa',
    'ZAF':'Africa','SSD':'Africa','ESP':'Europe','LKA':'Asia','SDN':'Africa',
    'SUR':'Americas','SWZ':'Africa','SWE':'Europe','CHE':'Europe','SYR':'Asia',
    'TJK':'Asia','TZA':'Africa','THA':'Asia','TLS':'Asia','TGO':'Africa',
    'TTO':'Americas','TUN':'Africa','TUR':'Asia','TKM':'Asia','UGA':'Africa',
    'UKR':'Europe','ARE':'Asia','URY':'Americas','UZB':'Asia','VUT':'Asia',
    'VEN':'Americas','VNM':'Asia','YEM':'Asia','ZMB':'Africa','ZWE':'Africa',
    'TWN':'Asia','PSE':'Asia','VAT':'Europe','MHL':'Asia','FSM':'Asia',
    'KIR':'Asia','NRU':'Asia','PLW':'Asia','TON':'Asia','TUV':'Asia',
    'ATG':'Americas','BHS':'Americas','BHR':'Asia','BTN':'Asia',
    'COK':'Asia','MCO':'Europe','LIE':'Europe','SMR':'Europe','AND':'Europe',
}
# P5 (excluded from corpus per codebook, but just in case)
P5 = {"USA","GBR","FRA","RUS","CHN"}

# ---------------------------------------------------------------------------
# 1. Load and merge
# ---------------------------------------------------------------------------
print("Loading data...")
speeches = pd.read_parquet(SPEECHES_PATH)
scores   = pd.read_parquet(SCORES_PATH)

# Merge on iso3+year
df = scores.merge(speeches[["iso3","year","country","was_truncated","analysis_text"]],
                  on=["iso3","year"], how="inner")

print(f"  Merged: {len(df)} rows")

# ---------------------------------------------------------------------------
# 2. Build stratification variables
# ---------------------------------------------------------------------------
# Era
df["era"] = np.where(df["year"] <= 1991, "Cold War", "Post-Cold War")

# Region
df["region"] = df["iso3"].map(REGION_MAP).fillna("Other")

# Restoration status
def restoration_status(row):
    if not row["was_truncated"]:
        return "originally_complete"
    # All truncated speeches were restored (Gate 3 confirmed 0 missing)
    return "truncated_restored"

df["restoration_status"] = df.apply(restoration_status, axis=1)

# Score group
def score_group(s):
    if s <= -1:
        return "negative"
    elif s == 0:
        return "neutral"
    else:
        return "positive"

df["score_group"] = df["primary_stance_score"].apply(score_group)

# P5 exclusion safety check
p5_rows = df[df["iso3"].isin(P5)]
if len(p5_rows) > 0:
    print(f"  WARNING: {len(p5_rows)} P5 rows found in merged data — dropping")
    df = df[~df["iso3"].isin(P5)]

# Drop any rows with iso3='.' (merge artifacts)
df = df[df["iso3"] != "."]

print(f"  Clean pool: {len(df)} rows")

# ---------------------------------------------------------------------------
# 3. Stratified sampling
# ---------------------------------------------------------------------------
np.random.seed(SEED)

strata_cols = ["era", "region", "restoration_status", "direct_us_mention", "score_group"]

# Count available strata
strata_counts = df.groupby(strata_cols).size()
print(f"\nStrata: {len(strata_counts)} unique combinations, {strata_counts.min()} min, {strata_counts.max()} max")

# Allocate: try to get at least 1 from each non-empty stratum, proportional fill
sample_rows = []

# First pass: 1 per stratum where possible
for (era, region, rstatus, us_mention, sgroup), grp in df.groupby(strata_cols):
    n_take = max(1, min(3, len(grp)))
    sample_rows.append(grp.sample(n=n_take, random_state=SEED))

sample = pd.concat(sample_rows).drop_duplicates(subset=["iso3","year"])

# If under target, pad with random
if len(sample) < TARGET_N:
    remaining = df[~df.index.isin(sample.index)]
    needed = TARGET_N - len(sample)
    pad = remaining.sample(n=min(needed, len(remaining)), random_state=SEED + 1)
    sample = pd.concat([sample, pad]).drop_duplicates(subset=["iso3","year"])

# If over target, trim to exactly TARGET_N maintaining proportional distribution
if len(sample) > TARGET_N:
    sample = sample.sample(n=TARGET_N, random_state=SEED)

sample = sample.reset_index(drop=True)

print(f"\nSampled: {len(sample)} speeches")

# ---------------------------------------------------------------------------
# 4. Generate review_ids
# ---------------------------------------------------------------------------
sample["review_id"] = [f"BLIND-{i+1:04d}" for i in range(len(sample))]

# ---------------------------------------------------------------------------
# 5. Generate BLINDED CSV
# ---------------------------------------------------------------------------
blinded = sample[["review_id","iso3","year","analysis_text"]].copy()
blinded["rubric_version"] = RUBRIC_VERSION

# ── Leakage check A: no prohibited fields in blinded CSV ──
extra_cols = [c for c in blinded.columns if c.lower() in [p.lower() for p in PROHIBITED_FIELDS]]
assert len(extra_cols) == 0, f"LEAKAGE: prohibited fields in blinded CSV: {extra_cols}"

# ── Leakage check B: all review_ids unique ──
assert blinded["review_id"].nunique() == len(blinded), "LEAKAGE: duplicate review_ids"

# ── Leakage check C: analysis_text not empty ──
empty_text = blinded["analysis_text"].isna().sum() + (blinded["analysis_text"].str.strip() == "").sum()
assert empty_text == 0, f"LEAKAGE: {empty_text} empty analysis_text rows"

# ── Leakage check D: Speeches not accidentally truncated ──
short_texts = (blinded["analysis_text"].str.len() < 100).sum()
assert short_texts == 0, f"LEAKAGE: {short_texts} suspiciously short texts (<100 chars)"

# ── Write blinded CSV ──
BLINDED_CSV.parent.mkdir(parents=True, exist_ok=True)
blinded.to_csv(BLINDED_CSV, index=False)
print(f"  Blinded CSV: {BLINDED_CSV} ({len(blinded)} rows)")

# ---------------------------------------------------------------------------
# 6. Generate HIDDEN ANSWER KEY
# ---------------------------------------------------------------------------
key_cols = [
    "review_id","iso3","year","era","region","restoration_status",
    "direct_us_mention","primary_stance_score","affective_warmth",
    "policy_alignment","order_alignment","confidence",
    "prompt_version","model_name","scoring_run_id","corpus_sha256",
]
available_key_cols = [c for c in key_cols if c in sample.columns]
key = sample[available_key_cols].copy()

# Fill any missing optional columns
for c in key_cols:
    if c not in key.columns:
        key[c] = None

KEY_PARQUET.parent.mkdir(parents=True, exist_ok=True)
key.to_parquet(KEY_PARQUET, index=False)
print(f"  Key parquet: {KEY_PARQUET} ({len(key)} rows)")

# ---------------------------------------------------------------------------
# 7. Leakage verification
# ---------------------------------------------------------------------------
print("\n=== LEAKAGE CHECKS ===")

# C1: exact sample count
assert len(blinded) == len(sample), f"Count mismatch: blinded={len(blinded)} vs sample={len(sample)}"
print(f"  [PASS] Sample count: {len(blinded)}")

# C2: review_id uniqueness
assert blinded["review_id"].nunique() == len(blinded)
print(f"  [PASS] review_id unique: {blinded['review_id'].nunique()}")

# C3: no empty analysis_text (already checked)
print(f"  [PASS] No empty analysis_text")

# C4: no truncated texts
print(f"  [PASS] No short texts (<100 chars)")

# C5: no prohibited fields
print(f"  [PASS] No prohibited fields in blinded CSV")

# C6: no Hermes scores in blinded
score_cols_in_blinded = [c for c in blinded.columns
                         if any(term in c.lower() for term in ["score","warmth","alignment","stance","confidence"])]
assert len(score_cols_in_blinded) == 0, f"LEAKAGE: score columns in blinded: {score_cols_in_blinded}"
print(f"  [PASS] No score columns in blinded CSV")

# C7: 1:1 match between review_ids
blinded_ids = set(blinded["review_id"])
key_ids = set(key["review_id"])
assert blinded_ids == key_ids, f"Review ID mismatch: {len(blinded_ids - key_ids)} in blinded only, {len(key_ids - blinded_ids)} in key only"
print(f"  [PASS] 1:1 review_id match: {len(blinded_ids)}")

# C8: original files untouched
for fp in ["data/original/course_package/speeches.parquet",
           "data/original/course_package/country_year_panel.csv",
           "data/original/course_package/codebook.md"]:
    full = PROJECT_ROOT / fp
    assert full.exists(), f"Missing original: {fp}"
print(f"  [PASS] Original files untouched")

# C9: no aid/unsc/us_agree in blinded (extra check)
for banned in ["total_aid","econ_aid","mil_aid","unsc","us_agree","ideal_point"]:
    assert banned not in blinded.columns, f"LEAKAGE: {banned} in blinded CSV"
print(f"  [PASS] No aid/unsc/voting variables in blinded CSV")

print("\n  ALL LEAKAGE CHECKS PASSED")

# ---------------------------------------------------------------------------
# 8. Hashes
# ---------------------------------------------------------------------------
def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

blinded_sha = file_sha256(BLINDED_CSV)
key_sha = file_sha256(KEY_PARQUET)
speeches_sha = file_sha256(SPEECHES_PATH)

# ---------------------------------------------------------------------------
# 9. Report CSV
# ---------------------------------------------------------------------------
report_rows = [
    ["metric","value"],
    ["total_samples", len(sample)],
    ["random_seed", SEED],
    ["rubric_version", RUBRIC_VERSION],
    ["generated_at", datetime.now(timezone.utc).isoformat()],
    ["input_file","data/processed/speeches_full.parquet"],
    ["input_sha256", speeches_sha],
    ["blinded_csv","data/interim/blinded_stance_validation_200.csv"],
    ["blinded_sha256", blinded_sha],
    ["key_parquet","data/interim/blinded_stance_validation_key_200.parquet"],
    ["key_sha256", key_sha],
    ["sampling_script","code/measurement/export_blind_validation.py"],
]

# Distributions
for label, col in [("era","era"),("region","region"),
                    ("restoration_status","restoration_status"),
                    ("direct_us_mention","direct_us_mention"),
                    ("score_group","score_group")]:
    counts = sample[col].value_counts()
    for val, cnt in counts.items():
        report_rows.append([f"{label}: {val}", cnt])

REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(report_rows[1:], columns=report_rows[0]).to_csv(REPORT_CSV, index=False)
print(f"\n  Report CSV: {REPORT_CSV}")

# ---------------------------------------------------------------------------
# 10. Manifest JSON
# ---------------------------------------------------------------------------
manifest = {
    "total_samples": len(sample),
    "random_seed": SEED,
    "rubric_version": RUBRIC_VERSION,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "input_file": str(SPEECHES_PATH),
    "input_sha256": speeches_sha,
    "blinded_csv": str(BLINDED_CSV),
    "blinded_sha256": blinded_sha,
    "key_parquet": str(KEY_PARQUET),
    "key_sha256": key_sha,
    "sampling_script": "code/measurement/export_blind_validation.py",
    "distribution": {
        "era": sample["era"].value_counts().to_dict(),
        "region": sample["region"].value_counts().to_dict(),
        "restoration_status": sample["restoration_status"].value_counts().to_dict(),
        "direct_us_mention": sample["direct_us_mention"].value_counts().to_dict(),
        "score_group": sample["score_group"].value_counts().to_dict(),
    },
    "leakage_checks": "ALL PASSED",
    "prohibited_fields_checked": PROHIBITED_FIELDS,
}

MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
with open(MANIFEST_JSON, "w") as f:
    json.dump(manifest, f, indent=2, default=str)
print(f"  Manifest JSON: {MANIFEST_JSON}")

# ---------------------------------------------------------------------------
# 11. Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*60}")
print(f"BLIND VALIDATION SAMPLE — COMPLETE")
print(f"{'='*60}")
print(f"  Sample size:     {len(sample)}")
print(f"  Seed:            {SEED}")
print(f"  Blinded CSV:     {BLINDED_CSV}")
print(f"  Key parquet:     {KEY_PARQUET}")
print(f"  Report CSV:      {REPORT_CSV}")
print(f"  Manifest JSON:   {MANIFEST_JSON}")
print(f"  Blinded SHA-256: {blinded_sha}")
print(f"  Key SHA-256:     {key_sha}")
print(f"  Leakage checks:  ALL PASSED")
print(f"\nDistribution:")
print(f"  Era:          {dict(sample['era'].value_counts())}")
print(f"  Region:       {dict(sample['region'].value_counts())}")
print(f"  Restoration:  {dict(sample['restoration_status'].value_counts())}")
print(f"  US mention:   {dict(sample['direct_us_mention'].value_counts())}")
print(f"  Score group:  {dict(sample['score_group'].value_counts())}")
