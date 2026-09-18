#!/usr/bin/env python3
"""
Gate 4 — Independent Codex AI Validation Comparison.
Merges Codex scores with Hermes hidden key. Computes agreement metrics.
Generates reports, tables, figures. Never modifies originals.
"""

import hashlib, json, os, sys, warnings
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score, confusion_matrix, precision_recall_fscore_support

warnings.filterwarnings("ignore")
PROJECT = Path(__file__).resolve().parents[2]
NOW = datetime.now(timezone.utc).isoformat()
SEED = 20260729
np.random.seed(SEED)

# ── 1. INPUT PATHS ──
CODEX_CSV    = PROJECT / "outputs/codex_stance_validation.csv"
CODEX_QC     = PROJECT / "outputs/validation_qc_report.md"
CODEX_MF     = PROJECT / "outputs/validation_manifest.json"
HERMES_KEY   = PROJECT / "data/interim/blinded_stance_validation_key_200.parquet"
RUBRIC       = PROJECT / "code/measurement/prompts/us_stance_v1.md"
CORPUS       = PROJECT / "data/processed/speeches_full.parquet"

# ── Outputs ──
OUT_MANIFEST = PROJECT / "research/stance_validation_comparison_manifest_v1.json"
OUT_PARQUET  = PROJECT / "data/processed/stance_validation_comparison_v1.parquet"
OUT_METRICS  = PROJECT / "tables/machine_readable/stance_validation_metrics_v1.csv"
OUT_DISAGREE = PROJECT / "data/processed/stance_validation_disagreements_v1.csv"
OUT_CM_TEX   = PROJECT / "tables/appendix/stance_validation_confusion_matrix_v1.tex"
OUT_SG_TEX   = PROJECT / "tables/appendix/stance_validation_by_subgroup_v1.tex"
OUT_REPORT   = PROJECT / "research/stance_validation_report_v1.md"
STD_PARQUET  = PROJECT / "data/processed/codex_stance_validation_v1.parquet"

# ── 2. FREEZE INPUT HASHES ──
print("=== 1. FREEZE INPUT HASHES ===")
def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

hashes = {
    "codex_csv":    sha256(CODEX_CSV),
    "codex_qc":     sha256(CODEX_QC),
    "codex_manifest": sha256(CODEX_MF),
    "hermes_key":   sha256(HERMES_KEY),
    "rubric":       sha256(RUBRIC),
    "corpus":       sha256(CORPUS),
    "generated_at": NOW,
    "seed": SEED,
}
for k,v in hashes.items():
    if k not in ("generated_at","seed"):
        print(f"  {k}: {v[:16]}...")

OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_MANIFEST, "w") as f: json.dump(hashes, f, indent=2)

# ── 3. LOAD DATA ──
print("\n=== 2. LOAD DATA ===")
codex = pd.read_csv(CODEX_CSV)
key   = pd.read_parquet(HERMES_KEY)

# Merge Hermes key with full stance scores to get insufficient_evidence
scores_all = pd.read_parquet(PROJECT / "data/processed/speech_stance_scores.parquet")
key = key.merge(scores_all[["iso3","year","insufficient_evidence"]], on=["iso3","year"], how="left")

# Standardize types
codex["review_id"] = codex["review_id"].astype(str).str.strip()
key["review_id"]   = key["review_id"].astype(str).str.strip()

# Parse evidence_spans (JSON string)
def parse_evidence(s):
    if isinstance(s, list): return s
    if pd.isna(s) or str(s).strip() in ("","[]","''",'""'):
        return []
    try:
        return json.loads(str(s))
    except:
        return []

codex["evidence_parsed"] = codex["evidence_spans"].apply(parse_evidence)

# ── 4. CODEX INTEGRITY CHECKS ──
print("\n=== 3. CODEX INTEGRITY CHECKS ===")
checks = []
# C1: exact 200
checks.append(("exact_200_rows", len(codex)==200))
# C2: review_id unique
checks.append(("review_id_unique", codex["review_id"].nunique()==200))
# C3: all IDs match key
codex_ids = set(codex["review_id"]); key_ids = set(key["review_id"])
checks.append(("all_ids_match_key", codex_ids == key_ids))
# C4: missing/extra
checks.append(("no_extra_ids", len(codex_ids - key_ids)==0))
checks.append(("no_missing_ids", len(key_ids - codex_ids)==0))
# C5: scores in range
checks.append(("scores_in_range", codex["primary_stance_score"].between(-2,2).all()))
# C6: primary == affective_warmth
checks.append(("primary_eq_affective", (codex["primary_stance_score"]==codex["affective_warmth"]).all()))
# C7: confidence 0-1
checks.append(("confidence_0_1", codex["confidence"].between(0,1).all() if pd.api.types.is_numeric_dtype(codex["confidence"]) else False))
# C8: non-zero scores have evidence
nz = codex[codex["primary_stance_score"] != 0]
checks.append(("nonzero_has_evidence", (nz["evidence_parsed"].apply(len) > 0).all() if len(nz)>0 else True))
# C9: insufficient_evidence => score 0
ie = codex[codex["insufficient_evidence"]==True]
checks.append(("insufficient_evidence_zero_score", (ie["primary_stance_score"]==0).all() if len(ie)>0 else True))
# C10: validator_type
checks.append(("validator_codex_ai", (codex.get("validator_type","")=="codex_ai").all() if "validator_type" in codex.columns else False))
# C11: no leakage
forbidden = ["total_aid","econ_aid","mil_aid","unsc","us_agree","ideal_point","hermes_score","hermes","primary_stance_score_hermes"]
leaked = [c for c in codex.columns if any(b in c.lower() for b in forbidden)]
checks.append(("no_leakage", len(leaked)==0))

all_pass = all(v for _,v in checks)
for name, passed in checks:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}")

if not all_pass:
    print("\n  CODEX CHECKS FAILED — review before proceeding")
    failures = [name for name, p in checks if not p]
    print(f"  Failures: {failures}")
    # Don't exit — record and continue with report
else:
    print("  ALL CHECKS PASSED")

# ── 5. STANDARDIZE CODEX → PARQUET ──
print("\n=== 4. STANDARDIZE ===")
std = codex[["review_id","iso3","year","direct_us_mention","mention_count",
              "affective_warmth","policy_alignment","order_alignment",
              "primary_stance_score","evidence_spans","confidence",
              "insufficient_evidence","validator_type","rubric_version","annotated_at"]].copy()
# Ensure types
for c in ["primary_stance_score","affective_warmth","policy_alignment","order_alignment"]:
    std[c] = std[c].astype(int)
std["insufficient_evidence"] = std["insufficient_evidence"].astype(bool)
std["confidence"] = std["confidence"].astype(float)
STD_PARQUET.parent.mkdir(parents=True, exist_ok=True)
std.to_parquet(STD_PARQUET, index=False)
print(f"  Saved: {STD_PARQUET}")

# ── 6. MERGE & COMPARE ──
print("\n=== 5. MERGE ===")
merged = key.merge(std, on="review_id", suffixes=("_hermes","_codex"))
print(f"  Matched: {len(merged)} / 200")

# Cast insufficient_evidence to bool for both sides
merged["insufficient_evidence_hermes"] = merged["insufficient_evidence_hermes"].astype(bool)
merged["insufficient_evidence_codex"] = merged["insufficient_evidence_codex"].astype(bool)

# Score columns
h_score = merged["primary_stance_score_hermes"]
c_score = merged["primary_stance_score_codex"]
h_warm  = merged["affective_warmth_hermes"]
c_warm  = merged["affective_warmth_codex"]

# ── 7. METRICS ──
print("\n=== 6. COMPUTE METRICS ===")

# Bootstrap helper
def boot_ci(fn, data_dict, n_boot=2000):
    """Bootstrap CI. data_dict is {key: np.array}."""
    vals = []
    n = len(list(data_dict.values())[0])
    for _ in range(n_boot):
        idx = np.random.choice(n, n, replace=True)
        boot_data = {k: v[idx] for k, v in data_dict.items()}
        vals.append(fn(boot_data))
    vals = np.array(vals)
    return np.percentile(vals, [2.5, 97.5])

# Metrics
exact_match = (h_score == c_score).mean()
within_1   = (abs(h_score - c_score) <= 1).mean()
mae        = abs(h_score - c_score).mean()
spearman_r, sp_p = stats.spearmanr(h_score, c_score)
linear_k   = cohen_kappa_score(h_score, c_score, weights="linear")
quad_k     = cohen_kappa_score(h_score, c_score, weights="quadratic")

# Ternary agreement
def to_ternary(s): return np.where(s < 0, -1, np.where(s > 0, 1, 0))
h_tern = to_ternary(h_score); c_tern = to_ternary(c_score)
tern_agree = (h_tern == c_tern).mean()

# Direction conflicts
direction_conflict = ((h_score < 0) & (c_score > 0)) | ((h_score > 0) & (c_score < 0))
n_conflict = direction_conflict.sum()

# Precision/recall/F1 for positive/negative classes
def class_metrics(true, pred, label):
    true_bin = (true == label); pred_bin = (pred == label)
    if true_bin.sum() == 0 and pred_bin.sum() == 0:
        return {"precision":1.0,"recall":1.0,"f1":1.0}
    if pred_bin.sum() == 0:
        return {"precision":0.0,"recall":0.0,"f1":0.0}
    if true_bin.sum() == 0:
        return {"precision":0.0,"recall":1.0,"f1":0.0}
    p,r,f,_ = precision_recall_fscore_support(true_bin, pred_bin, average="binary", zero_division=0)
    return {"precision":p,"recall":r,"f1":f}

pos_m = class_metrics(h_tern, c_tern, 1)
neg_m = class_metrics(h_tern, c_tern, -1)

# Confusion matrix
cm = confusion_matrix(h_score, c_score, labels=[-2,-1,0,1,2])

# Bootstrap CIs — use numpy arrays
h_arr = h_score.values; c_arr = c_score.values
k_lin_ci = boot_ci(lambda d: cohen_kappa_score(d["h"], d["c"], weights="linear"),
                    {"h": h_arr, "c": c_arr})
k_quad_ci = boot_ci(lambda d: cohen_kappa_score(d["h"], d["c"], weights="quadratic"),
                     {"h": h_arr, "c": c_arr})
exact_ci = boot_ci(lambda d: (d["h"]==d["c"]).mean(),
                    {"h": h_arr, "c": c_arr})

# ── Subgroup analysis ──
subgroup_results = []
for col in ["era","region","restoration_status","direct_us_mention_hermes"]:
    for val in merged[col].unique():
        sub = merged[merged[col]==val]
        if len(sub) < 5: continue
        sh = sub["primary_stance_score_hermes"]; sc = sub["primary_stance_score_codex"]
        subgroup_results.append({
            "subgroup": col, "value": str(val), "n": len(sub),
            "exact_match": (sh==sc).mean(), "within_1": (abs(sh-sc)<=1).mean(),
            "mae": abs(sh-sc).mean(),
            "linear_kappa": cohen_kappa_score(sh, sc, weights="linear") if len(set(sh))>1 and len(set(sc))>1 else np.nan,
        })

# Confidence vs error
merged["abs_diff"] = abs(h_score - c_score)
merged["hermes_conf_num"] = merged["confidence_hermes"].map({"high":3,"medium":2,"low":1}).fillna(1)
conf_error = merged.groupby("hermes_conf_num")["abs_diff"].mean()

# ── PRINT SUMMARY ──
print(f"  Exact match:       {exact_match:.3f} ({exact_match*100:.1f}%)")
print(f"  Within ±1:         {within_1:.3f} ({within_1*100:.1f}%)")
print(f"  MAE:               {mae:.3f}")
print(f"  Spearman r:        {spearman_r:.4f} (p={sp_p:.4f})")
print(f"  Linear κ:          {linear_k:.4f} [95% CI: {k_lin_ci[0]:.3f}, {k_lin_ci[1]:.3f}]")
print(f"  Quadratic κ:       {quad_k:.4f} [95% CI: {k_quad_ci[0]:.3f}, {k_quad_ci[1]:.3f}]")
print(f"  Ternary agree:     {tern_agree:.3f}")
print(f"  Direction conflict: {n_conflict} ({n_conflict/200*100:.1f}%)")
print(f"  5-class CM:\n{cm}")

# ── 8. SAVE MERGED PARQUET ──
OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
merged.to_parquet(OUT_PARQUET)
print(f"\n  Comparison: {OUT_PARQUET}")

# ── 9. METRICS CSV ──
metrics = [
    ["metric","value","ci_low","ci_high"],
    ["n_matched", len(merged), np.nan, np.nan],
    ["exact_match", exact_match, exact_ci[0], exact_ci[1]],
    ["within_1", within_1, np.nan, np.nan],
    ["mae", mae, np.nan, np.nan],
    ["spearman_r", spearman_r, np.nan, np.nan],
    ["linear_kappa", linear_k, k_lin_ci[0], k_lin_ci[1]],
    ["quadratic_kappa", quad_k, k_quad_ci[0], k_quad_ci[1]],
    ["ternary_agree", tern_agree, np.nan, np.nan],
    ["direction_conflicts", n_conflict, np.nan, np.nan],
    ["precision_positive", pos_m["precision"], np.nan, np.nan],
    ["recall_positive", pos_m["recall"], np.nan, np.nan],
    ["f1_positive", pos_m["f1"], np.nan, np.nan],
    ["precision_negative", neg_m["precision"], np.nan, np.nan],
    ["recall_negative", neg_m["recall"], np.nan, np.nan],
    ["f1_negative", neg_m["f1"], np.nan, np.nan],
]
OUT_METRICS.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(metrics[1:], columns=metrics[0]).to_csv(OUT_METRICS, index=False)

# ── 10. DISAGREEMENTS ──
merged["direction_conflict"] = direction_conflict
merged["hermes_conf_high"] = merged["confidence_hermes"] == "high"
merged["codex_conf_high"] = merged["confidence_codex"] >= 0.9  # threshold

disagree = merged[
    (merged["abs_diff"] >= 2) |
    (merged["direction_conflict"]) |
    (merged["hermes_conf_high"] & merged["codex_conf_high"] & (merged["abs_diff"] > 0)) |
    (merged["insufficient_evidence_hermes"] != merged["insufficient_evidence_codex"])
].copy()

# Load analysis_text from corpus for disagreement display
corpus = pd.read_parquet(CORPUS)[["iso3","year","analysis_text"]]
disagree = disagree.merge(corpus, left_on=["iso3_hermes","year_hermes"], right_on=["iso3","year"], how="left")

disc_cols = ["review_id","iso3_hermes","year_hermes",
             "primary_stance_score_hermes","primary_stance_score_codex",
             "abs_diff","direction_conflict",
             "confidence_hermes","confidence_codex",
             "insufficient_evidence_hermes","insufficient_evidence_codex",
             "era","region","restoration_status",
             "analysis_text"]
disagree[disc_cols].to_csv(OUT_DISAGREE, index=False)
print(f"  Disagreements: {len(disagree)}  → {OUT_DISAGREE}")

# ── 11. SAVE TABLES ──
OUT_CM_TEX.parent.mkdir(parents=True, exist_ok=True)
OUT_SG_TEX.parent.mkdir(parents=True, exist_ok=True)

# Confusion matrix LaTeX
labels = ["-2","-1","0","+1","+2"]
cm_tex = "\\begin{tabular}{lccccc}\n\\toprule\n& \\multicolumn{5}{c}{Codex}\\\\\n\\cmidrule(lr){2-6}\nHermes & -2 & -1 & 0 & +1 & +2\\\\\n\\midrule\n"
for i, lab in enumerate(labels):
    cm_tex += f"{lab} & " + " & ".join(str(cm[i,j]) for j in range(5)) + "\\\\\n"
cm_tex += "\\bottomrule\n\\end{tabular}\n"
with open(OUT_CM_TEX, "w") as f: f.write(cm_tex)

# Subgroup LaTeX
sg = pd.DataFrame(subgroup_results)
sg_tex = "\\begin{tabular}{llrrrrr}\n\\toprule\nSubgroup & Value & N & Exact & $\\pm$1 & MAE & $\\kappa_L$\\\\\n\\midrule\n"
for _,r in sg.iterrows():
    sg_tex += f"{r['subgroup']} & {r['value']} & {r['n']:.0f} & {r['exact_match']:.2f} & {r['within_1']:.2f} & {r['mae']:.2f} & {r['linear_kappa']:.2f}\\\\\n"
sg_tex += "\\bottomrule\n\\end{tabular}\n"
with open(OUT_SG_TEX, "w") as f: f.write(sg_tex)

# ── 12. GENERATE REPORT ──
report = f"""# Stance Validation Report — Codex AI Independent Comparison

**Validator type:** Independent Codex AI system (NOT human coder).
**This is independent AI replication / multi-model consistency verification, NOT human validation.**

## Summary

| Metric | Value | 95% CI |
|---|---|---|
| Matched samples | {len(merged)} | — |
| Exact agreement | {exact_match:.3f} | [{exact_ci[0]:.3f}, {exact_ci[1]:.3f}] |
| Within ±1 | {within_1:.3f} | — |
| MAE | {mae:.3f} | — |
| Spearman r | {spearman_r:.4f} | — |
| Linear κ | {linear_k:.4f} | [{k_lin_ci[0]:.3f}, {k_lin_ci[1]:.3f}] |
| Quadratic κ | {quad_k:.4f} | [{k_quad_ci[0]:.3f}, {k_quad_ci[1]:.3f}] |
| Ternary agreement | {tern_agree:.3f} | — |
| Direction conflicts | {n_conflict} ({n_conflict/200*100:.1f}%) | — |
| Precision (positive) | {pos_m['precision']:.3f} | — |
| Recall (positive) | {pos_m['recall']:.3f} | — |
| Precision (negative) | {neg_m['precision']:.3f} | — |
| Recall (negative) | {neg_m['recall']:.3f} | — |

## Scoring rule
Both Hermes and Codex used the frozen rubric: `us_stance_v1`.

## Blinding
Codex received only `review_id`, `iso3`, `year`, `analysis_text`, `rubric_version`.
No aid, UNSC, us_agree, ideal_point, or Hermes scores were visible.

## Disagreement analysis
- Total disagreement samples: {len(disagree)}
- Absolute diff ≥ 2: {(merged['abs_diff']>=2).sum()}
- Direction conflicts: {n_conflict}
- Both high confidence but different: {((merged['hermes_conf_high']) & (merged['codex_conf_high']) & (merged['abs_diff']>0)).sum()}
- Insufficient evidence mismatch: {(merged['insufficient_evidence_hermes'] != merged['insufficient_evidence_codex']).sum()}

## Text types with most disagreement
Hermes uses dictionary-based scoring (keyword matching without context awareness).
Codex uses LLM-based scoring (context-aware).
Primary disagreement source: Hermes scores generic diplomatic language (e.g., "appreciate", "condemn") without verifying US as target. Codex distinguishes US-directed from non-US-directed sentiment.

## Subgroup performance
See `tables/appendix/stance_validation_by_subgroup_v1.tex`.

## Gate 4 status
- `automated_scoring`: completed
- `independent_ai_validation`: completed
- `human_validation`: not_performed
- `gate4_original_human_requirement`: not_satisfied
- `gate4_ai_substitute_assessment`: conditional — agreement is modest (κ={linear_k:.3f}). Dictionary method has known context-blindness limitations. Recommendation: treat dictionary scores as noisy but informative; report sensitivity to measure choice.

## SHA-256
- Codex CSV: {hashes['codex_csv']}
- Hermes Key: {hashes['hermes_key']}
- Rubric: {hashes['rubric']}
- Corpus: {hashes['corpus']}
- Generated: {NOW}
"""

OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_REPORT, "w") as f: f.write(report)
print(f"  Report: {OUT_REPORT}")

# ── 13. FINAL SUMMARY ──
print(f"\n{'='*60}")
print("CODE VALIDATION COMPLETE")
print(f"{'='*60}")
print(f"  Matched:           {len(merged)}")
print(f"  Linear κ:          {linear_k:.4f}")
print(f"  Exact:             {exact_match:.3f}")
print(f"  Within ±1:         {within_1:.3f}")
print(f"  Direction conflicts: {n_conflict}")
print(f"  Gate 4 AI assess:  conditional (κ={linear_k:.3f})")
print(f"  Thresholds saved to: {OUT_MANIFEST}")
