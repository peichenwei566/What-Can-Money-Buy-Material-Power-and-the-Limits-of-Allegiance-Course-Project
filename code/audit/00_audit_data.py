#!/usr/bin/env python3
"""
Gate 1 — Integrity audit: course-package supplied data.

Reads exclusively from data/original/course_package/.
Writes machine-readable findings to manifests/data_audit.json
and an interpretive memo to research/data_audit.md.
"""

import json, os, sys
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
ORIG_DIR     = os.path.join(PROJECT_ROOT, "data", "original", "course_package")
PANEL_PATH   = os.path.join(ORIG_DIR, "country_year_panel.csv")
SPEECH_PATH  = os.path.join(ORIG_DIR, "speeches.parquet")
OUT_JSON     = os.path.join(PROJECT_ROOT, "manifests", "data_audit.json")
OUT_MD       = os.path.join(PROJECT_ROOT, "research", "data_audit.md")

os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------------
panel = pd.read_csv(PANEL_PATH)
speeches = pd.read_parquet(SPEECH_PATH)

report = {}

# ---------------------------------------------------------------------------
# 2. Panel basic dimensions
# ---------------------------------------------------------------------------
report["panel_rows"] = len(panel)
report["panel_columns"] = int(panel.shape[1])
report["panel_cols"] = list(panel.columns)
report["panel_dtypes"] = {c: str(panel[c].dtype) for c in panel.columns}
report["panel_year_min"] = int(panel["year"].min())
report["panel_year_max"] = int(panel["year"].max())
report["panel_countries"] = int(panel["iso3"].nunique())

# ---------------------------------------------------------------------------
# 3. Speech basic dimensions
# ---------------------------------------------------------------------------
report["speech_rows"] = len(speeches)
report["speech_columns"] = int(speeches.shape[1])
report["speech_cols"] = list(speeches.columns)
report["speech_dtypes"] = {c: str(speeches[c].dtype) for c in speeches.columns}
report["speech_year_min"] = int(speeches["year"].min())
report["speech_year_max"] = int(speeches["year"].max())
report["speech_countries"] = int(speeches["iso3"].nunique())

# ---------------------------------------------------------------------------
# 4. Duplicate keys
# ---------------------------------------------------------------------------
panel_dupes = panel[panel.duplicated(subset=["iso3","year"], keep=False)]
report["panel_duplicate_keys"] = len(panel_dupes)
report["panel_duplicate_examples"] = (
    panel_dupes[["iso3","year"]].drop_duplicates().head(10).to_dict("records")
    if len(panel_dupes) > 0 else []
)

speech_dupes = speeches[speeches.duplicated(subset=["iso3","year"], keep=False)]
report["speech_duplicate_keys"] = len(speech_dupes)
report["speech_duplicate_examples"] = (
    speech_dupes[["iso3","year"]].drop_duplicates().head(10).to_dict("records")
    if len(speech_dupes) > 0 else []
)

# ---------------------------------------------------------------------------
# 5. Malformed / missing ISO codes
# ---------------------------------------------------------------------------
# Check iso3 values against the known set of 179 countries in the codebook
known_iso3 = panel["iso3"].unique()
all_iso3 = set(speeches["iso3"].unique()) | set(panel["iso3"].unique())

non_standard = []
bad_patterns = [".", "", "nan", "NaN", "NA", "N/A", "none", "None", "null"]
for code in sorted(all_iso3):
    if pd.isna(code) or str(code).strip() in bad_patterns or len(str(code).strip()) != 3:
        non_standard.append(str(code))
    elif not str(code).strip().isupper():
        non_standard.append(str(code))

report["non_standard_iso3"] = non_standard

# ---------------------------------------------------------------------------
# 6. Missingness by column
# ---------------------------------------------------------------------------
def missing_summary(df, name):
    miss = df.isnull().sum()
    miss_pct = (miss / len(df) * 100).round(2)
    out = {}
    for col in df.columns:
        if miss[col] > 0:
            out[col] = {"missing": int(miss[col]), "pct": float(miss_pct[col])}
    return out

report["panel_missing"] = missing_summary(panel, "panel")
report["speech_missing"] = missing_summary(speeches, "speeches")

# ---------------------------------------------------------------------------
# 7. Truncated speeches
# ---------------------------------------------------------------------------
if "truncated" in speeches.columns:
    truncated_count = int(speeches["truncated"].sum())
    report["truncated_count"] = truncated_count
    report["truncated_share"] = round(truncated_count / len(speeches), 4)
    report["truncated_pct"] = round(truncated_count / len(speeches) * 100, 2)
else:
    report["truncated_count"] = None
    report["truncated_share"] = None

# ---------------------------------------------------------------------------
# 8. Speech-to-panel join
# ---------------------------------------------------------------------------
merged = speeches.merge(panel, on=["iso3","year"], how="left", indicator=True)
join_summary = merged["_merge"].value_counts().to_dict()
join_summary = {k: int(v) for k, v in join_summary.items()}
report["speech_panel_join"] = join_summary

matched_speeches = join_summary.get("both", 0)
report["speech_join_rate"] = round(matched_speeches / len(speeches), 4)

# ---------------------------------------------------------------------------
# 9. Aid consistency: total_aid == econ_aid + mil_aid
# ---------------------------------------------------------------------------
panel["computed_total"] = panel["econ_aid"].fillna(0) + panel["mil_aid"].fillna(0)
aid_mismatch = panel[
    (panel["total_aid"].fillna(0) - panel["computed_total"]).abs() > 0.01
]
report["aid_consistency_mismatch_count"] = len(aid_mismatch)
if len(aid_mismatch) > 0:
    report["aid_mismatch_examples"] = aid_mismatch[
        ["iso3","year","total_aid","econ_aid","mil_aid","computed_total"]
    ].head(10).to_dict("records")
else:
    report["aid_mismatch_examples"] = []

# ---------------------------------------------------------------------------
# 10. Negative / zero aid
# ---------------------------------------------------------------------------
neg_total = int((panel["total_aid"] < 0).sum())
zero_total = int((panel["total_aid"] == 0).sum())
neg_econ = int((panel["econ_aid"].fillna(0) < 0).sum())
neg_mil = int((panel["mil_aid"].fillna(0) < 0).sum())
report["total_aid_negative"] = neg_total
report["total_aid_zero"] = zero_total
report["econ_aid_negative"] = neg_econ
report["mil_aid_negative"] = neg_mil

# ---------------------------------------------------------------------------
# 11. P5 presence (should be zero)
# ---------------------------------------------------------------------------
p5 = {"USA", "GBR", "FRA", "RUS", "CHN", "RUS"}
panel_p5 = panel[panel["iso3"].isin(p5)]
speech_p5 = speeches[speeches["iso3"].isin(p5)]
report["panel_p5_rows"] = len(panel_p5)
report["speech_p5_rows"] = len(speech_p5)
if len(panel_p5) > 0:
    report["panel_p5_examples"] = panel_p5[["iso3","year"]].head(5).to_dict("records")
if len(speech_p5) > 0:
    report["speech_p5_examples"] = speech_p5[["iso3","year"]].head(5).to_dict("records")

# ---------------------------------------------------------------------------
# 12. Codebook checks — does the panel have 11 columns as described?
# ---------------------------------------------------------------------------
report["panel_col_count_codebook"] = 11
report["panel_col_count_actual"] = int(panel.shape[1])

# Expected columns from codebook
expected_cols = ["iso3", "country", "year", "unsc", "econ_aid", "mil_aid",
                 "total_aid", "us_agree", "china_agree", "russia_agree", "ideal_point"]
actual_cols = list(panel.columns)
present = [c for c in expected_cols if c in actual_cols]
missing = [c for c in expected_cols if c not in actual_cols]
extra = [c for c in actual_cols if c not in expected_cols]
report["codebook_cols_present"] = present
report["codebook_cols_missing"] = missing
report["codebook_cols_extra"] = extra

# Speech columns check
expected_speech_cols = ["iso3", "country", "year", "n_words", "n_chars_full", "truncated", "text"]
speech_present = [c for c in expected_speech_cols if c in speeches.columns]
speech_missing = [c for c in expected_speech_cols if c not in speeches.columns]
report["speech_codebook_cols_present"] = speech_present
report["speech_codebook_cols_missing"] = speech_missing

# ---------------------------------------------------------------------------
# 13. Year range check — should be 1970-2020
# ---------------------------------------------------------------------------
report["panel_year_range_ok"] = (report["panel_year_min"] == 1970 and report["panel_year_max"] == 2020)
report["speech_year_range_ok"] = (report["speech_year_min"] == 1970 and report["speech_year_max"] == 2020)

# ---------------------------------------------------------------------------
# Write JSON
# ---------------------------------------------------------------------------
with open(OUT_JSON, "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"Wrote {OUT_JSON}")

# ---------------------------------------------------------------------------
# Write Markdown memo
# ---------------------------------------------------------------------------
lines = []
lines.append("# Data Audit — Gate 1")
lines.append("")
lines.append(f"**Panel:** {report['panel_rows']} rows × {report['panel_columns']} columns")
lines.append(f"  - Year range: {report['panel_year_min']}–{report['panel_year_max']}")
lines.append(f"  - Unique countries: {report['panel_countries']}")
lines.append(f"  - Duplicate (iso3, year) keys: {report['panel_duplicate_keys']}")
lines.append(f"  - Codebook column check: {len(report['codebook_cols_present'])}/{len(expected_cols)} present")
if report['codebook_cols_missing']:
    lines.append(f"  - MISSING from codebook: {report['codebook_cols_missing']}")
if report['codebook_cols_extra']:
    lines.append(f"  - EXTRA columns: {report['codebook_cols_extra']}")
if report['panel_missing']:
    lines.append(f"  - Missing values by column:")
    for col, info in report['panel_missing'].items():
        lines.append(f"    - {col}: {info['missing']} ({info['pct']}%)")
lines.append("")
lines.append(f"**Speeches:** {report['speech_rows']} rows × {report['speech_columns']} columns")
lines.append(f"  - Year range: {report['speech_year_min']}–{report['speech_year_max']}")
lines.append(f"  - Unique countries: {report['speech_countries']}")
lines.append(f"  - Duplicate (iso3, year) keys: {report['speech_duplicate_keys']}")
lines.append(f"  - Truncated: {report['truncated_count']} ({report['truncated_pct']}%)")
lines.append(f"  - Speech-to-panel join (both match): {report['speech_join_rate']*100:.1f}%")
if report['speech_missing']:
    lines.append(f"  - Missing columns (vs codebook): {report['speech_missing']}")
if report['speech_missing']:
    lines.append(f"  - Missing values by column:")
    for col, info in report['speech_missing'].items():
        lines.append(f"    - {col}: {info['missing']} ({info['pct']}%)")
lines.append("")
lines.append("**Key checks:**")
lines.append(f"  - Non-standard ISO codes: {report['non_standard_iso3']}")
lines.append(f"  - Aid consistency (total_aid vs econ+mil): {report['aid_consistency_mismatch_count']} mismatches")
lines.append(f"  - total_aid negative: {report['total_aid_negative']}, zero: {report['total_aid_zero']}")
lines.append(f"  - econ_aid negative: {report['econ_aid_negative']}")
lines.append(f"  - mil_aid negative: {report['mil_aid_negative']}")
lines.append(f"  - P5 in panel: {report['panel_p5_rows']} rows, in speeches: {report['speech_p5_rows']} rows")
lines.append("")
lines.append("### Decisions required")
lines.append("")
if report['panel_duplicate_keys'] > 0:
    lines.append(f"- **{report['panel_duplicate_keys']} duplicate panel keys** — need review and decision per .hermes.md rule 25.")
if report['speech_duplicate_keys'] > 0:
    lines.append(f"- **{report['speech_duplicate_keys']} duplicate speech keys** — need review and decision per .hermes.md rule 25.")
if report['non_standard_iso3']:
    lines.append(f"- **Non-standard ISO codes** — investigate: {report['non_standard_iso3']}")
if report['aid_consistency_mismatch_count'] > 0:
    lines.append(f"- **{report['aid_consistency_mismatch_count']} aid consistency mismatches** — investigate if de-obligations explain differences.")
if report['panel_p5_rows'] > 0:
    lines.append(f"- **P5 rows found in panel** — codebook says P5 are excluded. Investigate.")
if report['speech_p5_rows'] > 0:
    lines.append(f"- **P5 rows found in speeches** — codebook says P5 are excluded. Investigate.")

lines.append("")
lines.append(f"*Script: code/audit/00_audit_data.py*")

with open(OUT_MD, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"Wrote {OUT_MD}")
print("Audit complete.")
