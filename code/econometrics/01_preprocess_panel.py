#!/usr/bin/env python3
"""
Gate 5 — Preprocess analysis panel (v3.1 scores, real 2020 USD aid).
  No external controls — relies on country + year fixed effects.
"""

import hashlib, sys, warnings
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

warnings.filterwarnings("ignore")
PROJECT = Path(__file__).resolve().parents[2]
P5 = {"USA","GBR","FRA","RUS","CHN"}
NOW = datetime.now(timezone.utc)

# ── 1. LOAD CPI DEFLATOR ──
print("1. CPI DEFLATOR")
cpi = pd.read_csv(PROJECT / "data/interim/us_cpi_deflator.csv")
cpi_map = dict(zip(cpi["year"], cpi["cpi_2020"]))
print(f"   {len(cpi_map)} years ({min(cpi_map)}–{max(cpi_map)})")

# ── 2. LOAD ALL SOURCES ──
print("\n2. LOAD & MERGE")
scores   = pd.read_parquet(PROJECT / "data/processed/speech_stance_scores_v3_1.parquet")
speeches = pd.read_parquet(PROJECT / "data/processed/speeches_full.parquet")
panel_raw = pd.read_csv(PROJECT / "data/original/course_package/country_year_panel.csv")

panel = panel_raw[~panel_raw["iso3"].isin(P5) & (panel_raw["iso3"] != ".")].copy()

df = scores.merge(speeches[["iso3","year","was_truncated","replacement_status"]],
                   on=["iso3","year"], how="left")
df = df.merge(panel, on=["iso3","year"], how="left")
print(f"   Merged: {df.shape[0]:,} rows, {df['iso3'].nunique()} countries")

# ── 3. DEFLATE AID nominal → real 2020 USD ──
print("\n3. DEFLATE AID → real 2020 USD")
df["deflator"] = 100.0 / df["year"].map(cpi_map)
for col in ["econ_aid","mil_aid","total_aid"]:
    df[f"{col}_real"] = df[col].fillna(0).clip(lower=0) * df["deflator"]
    df[f"log_{col}_real"] = np.log1p(df[f"{col}_real"])
df["log_total_aid"] = df["log_total_aid_real"]

# Verify
samp = df[df["total_aid"]>1000].head(3)
for _,r in samp.iterrows():
    print(f"   {r['iso3']} {int(r['year'])}: ${r['total_aid']:,.0f} → ${r['total_aid_real']:,.0f}")

# ── 4. DERIVED VARIABLES ──
df["stance"] = df["primary_stance_score"]
df["cold_war"] = (df["year"] <= 1991).astype(int)
df["post_2001"] = (df["year"] >= 2001).astype(int)
df["sample_verified"] = (~df["was_truncated"] | df["replacement_status"].isin(
    ["exact-prefix","normalized-prefix"])).astype(int)
df["sample_original"] = (~df["was_truncated"]).astype(int)

# ── 5. SAVE ──
out = PROJECT / "data/processed/analysis_panel_v3_1.parquet"
df.to_parquet(out)

panel_hash = hashlib.sha256(open(out,"rb").read()).hexdigest()
print(f"\n   Saved: {out}")
print(f"   SHA-256: {panel_hash}")

# ── 6. SUMMARY ──
d = df.dropna(subset=["stance","log_total_aid","unsc"])
print(f"\n   Analysis sample: N={len(d):,}  countries={d['iso3'].nunique()}")
print(f"   UNSC=1: {(d['unsc']==1).sum():,} ({d['unsc'].mean()*100:.1f}%)")
print(f"   Stance mean={d['stance'].mean():.3f} sd={d['stance'].std():.3f}")
print(f"   Real aid mean=${d['total_aid_real'].mean():,.0f}")
print(f"   {NOW.isoformat()}")
