#!/usr/bin/env python3
"""
Gate 5 — Rebuild analysis panel with WDI controls + real aid + v3.1 scores.
Controls: log GDP per capita, log population, trade openness (% GDP).
"""

import hashlib, sys, warnings, numpy as np, pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import statsmodels.formula.api as smf
from statsmodels.stats.sandwich_covariance import cov_cluster
from scipy import stats

warnings.filterwarnings("ignore")
PROJECT = Path(__file__).resolve().parents[2]
P5 = {"USA","GBR","FRA","RUS","CHN"}
NOW = datetime.now(timezone.utc)

# ── 1. LOAD + MERGE ──
print("1. LOAD & MERGE")
cpi = pd.read_csv(PROJECT / "data/interim/us_cpi_deflator.csv")
cpi_map = dict(zip(cpi["year"], cpi["cpi_2020"]))

scores   = pd.read_parquet(PROJECT / "data/processed/speech_stance_scores_v3_1.parquet")
speeches = pd.read_parquet(PROJECT / "data/processed/speeches_full.parquet")
panel    = pd.read_csv(PROJECT / "data/original/course_package/country_year_panel.csv")
wdi      = pd.read_parquet(PROJECT / "data/interim/wdi_controls_v2.parquet")

wdi_wide = wdi.pivot_table(index=["iso3","year"], columns="indicator", values="value").reset_index()

df = scores.merge(speeches[["iso3","year","was_truncated","replacement_status"]],
                   on=["iso3","year"], how="left")
df = df.merge(panel, on=["iso3","year"], how="left")
df = df.merge(wdi_wide, on=["iso3","year"], how="left")
print(f"   Merged: {df.shape[0]:,} rows")

# ── 2. DEFLATE + DERIVE ──
df["deflator"] = 100.0 / df["year"].map(cpi_map)
for col in ["econ_aid","mil_aid","total_aid"]:
    df[f"{col}_real"] = df[col].fillna(0).clip(lower=0) * df["deflator"]
    df[f"log_{col}_real"] = np.log1p(df[f"{col}_real"])
df["log_total_aid"] = df["log_total_aid_real"]
df["stance"] = df["primary_stance_score"]

# Controls
for c in ["gdp_pc_2015usd","population","trade_pct_gdp"]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
df["log_gdp_pc"] = np.log(df["gdp_pc_2015usd"].clip(lower=1))
df["log_pop"] = np.log(df["population"].clip(lower=1))

df["cold_war"] = (df["year"] <= 1991).astype(int)
df["post_2001"] = (df["year"] >= 2001).astype(int)
df["sample_verified"] = (~df["was_truncated"] | df["replacement_status"].isin(
    ["exact-prefix","normalized-prefix"])).astype(int)
df["sample_original"] = (~df["was_truncated"]).astype(int)

# ── 3. SAVE PANEL ──
out = PROJECT / "data/processed/analysis_panel_v3_1.parquet"
df.to_parquet(out)
ph = hashlib.sha256(open(out,"rb").read()).hexdigest()
print(f"   Saved: {out}\n   SHA-256: {ph}")

# ── 4. ANALYSIS SAMPLES ──
BASE_VARS = ["stance","log_total_aid","unsc"]
d_fe = df.dropna(subset=BASE_VARS)
d_ctl = df.dropna(subset=BASE_VARS + ["log_gdp_pc","log_pop","trade_pct_gdp"])

print(f"\n   FE-only: N={len(d_fe):,}  control: N={len(d_ctl):,}")

# ── 5. RUN REGRESSIONS ──
def run_fe(y, x_vars, data, label):
    formula = f"{y} ~ {' + '.join(x_vars)} + C(iso3) + C(year)"
    sub = data.dropna(subset=[y] + x_vars)
    mod = smf.ols(formula, data=sub).fit()
    cov = cov_cluster(mod, sub["iso3"].values)
    se_cl = np.sqrt(np.diag(cov))
    out = {}
    for var in x_vars:
        idx = list(mod.params.index).index(var)
        b, s = mod.params[var], se_cl[idx]
        out[var] = {"coef":b,"se":s,"ci_low":b-1.96*s,"ci_high":b+1.96*s,
                     "t":b/s,"p":2*stats.t.sf(abs(b/s), mod.df_resid),
                     "n":int(mod.nobs),"n_countries":sub.iso3.nunique(),"r2":mod.rsquared}
    if x_vars:
        out["_f_stat"] = out[x_vars[0]]["t"]**2
    return out, mod

results = []

CONTROLS = ["log_gdp_pc","log_pop","trade_pct_gdp"]

# FS
print("\n=== FIRST STAGE ===")
for label, data in [("FE_only", d_fe), ("+controls", d_ctl)]:
    x_vars = ["unsc"] if label == "FE_only" else ["unsc"] + CONTROLS
    out, _ = run_fe("log_total_aid", x_vars, data, label)
    r = out["unsc"]
    results.append({"model":f"first_stage_{label}","outcome":"log_total_aid_real",
        "coef":r["coef"],"se":r["se"],"ci_low":r["ci_low"],"ci_high":r["ci_high"],
        "t":r["t"],"p":r["p"],"f_stat":out["_f_stat"],"n":r["n"],"n_countries":r["n_countries"],
        "r2":r["r2"],"sample":label,"controls":"+".join(x_vars[1:])})
    print(f"  [{label:12s}] coef={r['coef']:7.4f} se={r['se']:.4f} F={out['_f_stat']:.1f} N={r['n']}")

# RF
print("\n=== REDUCED FORM ===")
for label, data in [("FE_only", d_fe), ("+controls", d_ctl)]:
    x_vars = ["unsc"] if label == "FE_only" else ["unsc"] + CONTROLS
    out, _ = run_fe("stance", x_vars, data, label)
    r = out["unsc"]
    results.append({"model":f"reduced_form_{label}","outcome":"stance",
        "coef":r["coef"],"se":r["se"],"ci_low":r["ci_low"],"ci_high":r["ci_high"],
        "t":r["t"],"p":r["p"],"n":r["n"],"n_countries":r["n_countries"],
        "r2":r["r2"],"sample":label,"controls":"+".join(x_vars[1:])})
    stars = "***" if r["p"]<0.01 else "**" if r["p"]<0.05 else "*" if r["p"]<0.1 else ""
    print(f"  [{label:12s}] coef={r['coef']:7.4f} se={r['se']:.4f} p={r['p']:.4f}{stars} N={r['n']}")

# ── 6. SAVE ──
res_df = pd.DataFrame(results)
res_df["corpus_version"] = "data-restored-v1"
res_df["stance_version"] = "stance-measure-v3.1"
res_df["run_id"] = f"gate5-{NOW.isoformat()[:19]}"
res_df["panel_sha256"] = ph

out_csv = PROJECT / "tables/machine_readable/gate5_v3_1_all_results.csv"
res_df.to_csv(out_csv, index=False)
print(f"\nSaved: {out_csv} ({len(res_df)} rows)")

print(f"\n{'='*60}")
print("GATE 5 COMPLETE")
print(f"{'='*60}")
fs = res_df[res_df["model"]=="first_stage_FE_only"].iloc[0]
rf = res_df[res_df["model"]=="reduced_form_FE_only"].iloc[0]
print(f"First stage:  F={fs['f_stat']:.1f}")
print(f"Reduced form: coef={rf['coef']:.4f} p={rf['p']:.4f}")
print(f"Causal gate:  {'OPEN' if fs['f_stat']>10 else 'CLOSED'}")
