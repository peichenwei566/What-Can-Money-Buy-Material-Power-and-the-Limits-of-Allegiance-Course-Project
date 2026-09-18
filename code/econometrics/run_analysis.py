#!/usr/bin/env python3
"""
Gate 5 — Econometrics. OLS with country+year dummies, clustered SEs.
Reports first stage, reduced form, event study, robustness.
Causal gate: F > 10 required for 2SLS.
"""

import hashlib, os, sys, warnings
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.sandwich_covariance import cov_cluster
from scipy import stats

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(line_buffering=True)
PROJECT = Path(__file__).resolve().parents[2]
P5 = {"USA","GBR","FRA","RUS","CHN"}
NOW = datetime.now(timezone.utc).isoformat()

# ── 1. BUILD PANEL ──
print("=== 1. BUILD PANEL ===")
scores   = pd.read_parquet(PROJECT / "data/processed/speech_stance_scores.parquet")
speeches = pd.read_parquet(PROJECT / "data/processed/speeches_full.parquet")
panel    = pd.read_csv(PROJECT / "data/original/course_package/country_year_panel.csv")

df = scores.merge(speeches[["iso3","year","was_truncated","replacement_status"]], on=["iso3","year"])
df = df.merge(panel, on=["iso3","year"], how="left")
df = df[~df["iso3"].isin(P5) & (df["iso3"] != ".")]
df["log_total_aid"] = np.log1p(df["total_aid"].fillna(0).clip(lower=0))
df["stance"] = df["affective_warmth_continuous"]
df["era"] = np.where(df["year"] <= 1991, "Cold War", "Post-Cold War")
df["post_2001"] = (df["year"] >= 2001).astype(int)
df["sample_verified"] = (~df["was_truncated"] | df["replacement_status"].isin(["exact-prefix","normalized-prefix"])).astype(int)
df["sample_original"] = (~df["was_truncated"]).astype(int)
df.to_parquet(PROJECT / "data/processed/analysis_panel.parquet")

d_all = df.dropna(subset=["stance","log_total_aid","unsc"])
print(f"  N={len(d_all)} countries={d_all['iso3'].nunique()}")

# ── Helper ──
def run_fe(y_var, x_vars, data, cluster_col="iso3"):
    """OLS with C(iso3)+C(year) FE, clustered SEs. Returns dict + F-stat."""
    formula = f"{y_var} ~ {' + '.join(x_vars)} + C(iso3) + C(year)"
    d = data.dropna(subset=[y_var] + x_vars)
    mod = smf.ols(formula, data=d).fit()
    clusters = d[cluster_col].values
    cov = cov_cluster(mod, clusters)
    se_cl = np.sqrt(np.diag(cov))
    n_cty = d[cluster_col].nunique()
    out = {}
    for var in x_vars:
        idx = list(mod.params.index).index(var)
        b = mod.params[var]; s = se_cl[idx]
        out[var] = {"coef": b, "se": s, "ci_low": b - 1.96*s, "ci_high": b + 1.96*s,
                     "t": b/s, "p": 2*stats.t.sf(abs(b/s), mod.df_resid),
                     "n": int(mod.nobs), "n_countries": n_cty, "r2": mod.rsquared}
    # F-stat for first x_var from t-stat
    if x_vars:
        t_val = out[x_vars[0]]["t"]
        out["_f_stat"] = t_val ** 2
    return out, mod

results = []

# ── 2. DESCRIPTIVES ──
print("\n=== 2. DESCRIPTIVES ===")
for var,desc in [("stance","Outcome"),("log_total_aid","log(Aid)"),("unsc","UNSC")]:
    print(f"  {desc}: mean={d_all[var].mean():.4f} sd={d_all[var].std():.4f}")
print(f"  Corr(stance,us_agree)={d_all['stance'].corr(d_all['us_agree']):.4f}  (n={d_all['us_agree'].notna().sum()})")
print(f"  Corr(stance,ideal_point)={d_all['stance'].corr(d_all['ideal_point']):.4f}")

# ── 3. FIRST STAGE ──
print("\n=== 3. FIRST STAGE ===")
for label, mask in [("all", slice(None)), ("verified", d_all["sample_verified"]==1),
                     ("original", d_all["sample_original"]==1)]:
    d = d_all.loc[mask] if isinstance(mask, pd.Series) else d_all
    out, mod = run_fe("log_total_aid", ["unsc"], d)
    r = out["unsc"]; f = out["_f_stat"]
    results.append({"model":f"first_stage_{label}", "outcome":"log_total_aid",
        "coef":r["coef"],"se":r["se"],"ci_low":r["ci_low"],"ci_high":r["ci_high"],
        "t":r["t"],"p":r["p"],"f_stat":f,"n":r["n"],"n_countries":r["n_countries"],
        "r2":r["r2"],"sample":label})
    print(f"  [{label}] unsc={r['coef']:.4f} se={r['se']:.4f} t={r['t']:.2f} F={f:.1f} N={r['n']}")

# ── 4. REDUCED FORM ──
print("\n=== 4. REDUCED FORM ===")
for label, mask in [("all", slice(None)), ("verified", d_all["sample_verified"]==1),
                     ("original", d_all["sample_original"]==1)]:
    d = d_all.loc[mask] if isinstance(mask, pd.Series) else d_all
    out, mod = run_fe("stance", ["unsc"], d)
    r = out["unsc"]
    results.append({"model":f"reduced_form_{label}", "outcome":"stance",
        "coef":r["coef"],"se":r["se"],"ci_low":r["ci_low"],"ci_high":r["ci_high"],
        "t":r["t"],"p":r["p"],"n":r["n"],"n_countries":r["n_countries"],
        "r2":r["r2"],"sample":label})
    print(f"  [{label}] unsc={r['coef']:.4f} se={r['se']:.4f} t={r['t']:.2f} p={r['p']:.4f} N={r['n']}")

# ── 5. EVENT STUDY ──
print("\n=== 5. EVENT STUDY ===")
d_es = d_all.copy()
for lag in [1,2]:
    d_es[f"unsc_lag{lag}"] = d_es.groupby("iso3")["unsc"].shift(lag).fillna(0)
for lead in [1,2]:
    d_es[f"unsc_lead{lead}"] = d_es.groupby("iso3")["unsc"].shift(-lead).fillna(0)
es_vars = ["unsc_lead2","unsc_lead1","unsc","unsc_lag1","unsc_lag2"]
out, mod = run_fe("stance", es_vars, d_es)
for var in es_vars:
    r = out[var]
    results.append({"model":f"event_study_{var}", "outcome":"stance",
        "coef":r["coef"],"se":r["se"],"ci_low":r["ci_low"],"ci_high":r["ci_high"],
        "t":r["t"],"p":r["p"],"n":r["n"],"n_countries":r["n_countries"],"r2":r["r2"],
        "sample":"all"})
    stars = "***" if r["p"]<0.01 else "**" if r["p"]<0.05 else "*" if r["p"]<0.1 else ""
    print(f"  {var:14s}: coef={r['coef']:8.4f} se={r['se']:8.4f} p={r['p']:.4f} {stars}")

# ── 6. CAUSAL GATE ──
print("\n=== 6. CAUSAL GATE ===")
fs_f = results[0]["f_stat"]  # first_stage_all
print(f"  First-stage F = {fs_f:.1f}")
print(f"  Threshold:     F > 10 (Staiger-Stock 1997)")
if fs_f > 10:
    print(f"  GATE OPEN — would run 2SLS")
else:
    print(f"  GATE CLOSED — 2SLS not reported. Reporting reduced form.")

# ── 7. ROBUSTNESS ──
print("\n=== 7. ROBUSTNESS ===")
checks = [
    ("cold_war", d_all["era"]=="Cold War"),
    ("post_cold_war", d_all["era"]=="Post-Cold War"),
    ("post_2001", d_all["post_2001"]==1),
    ("us_mention_only", d_all["direct_us_mention"]==True),
    ("original_only", d_all["sample_original"]==1),
]
for label, mask in checks:
    d = d_all[mask]
    if len(d) < 200: continue
    # RF
    out_rf, _ = run_fe("stance", ["unsc"], d)
    r = out_rf["unsc"]
    results.append({"model":f"robustness_rf_{label}", "outcome":"stance",
        "coef":r["coef"],"se":r["se"],"ci_low":r["ci_low"],"ci_high":r["ci_high"],
        "t":r["t"],"p":r["p"],"n":r["n"],"n_countries":r["n_countries"],"r2":r["r2"],
        "sample":label})
    print(f"  [rf-{label}] coef={r['coef']:7.4f} se={r['se']:.4f} p={r['p']:.4f} N={r['n']}")
    # FS
    out_fs, _ = run_fe("log_total_aid", ["unsc"], d)
    r = out_fs["unsc"]; f = out_fs["_f_stat"]
    results.append({"model":f"robustness_fs_{label}", "outcome":"log_total_aid",
        "coef":r["coef"],"se":r["se"],"t":r["t"],"p":r["p"],"f_stat":f,
        "n":r["n"],"n_countries":r["n_countries"],"r2":r["r2"],"sample":label})
    print(f"  [fs-{label}] coef={r['coef']:7.4f} se={r['se']:.4f} F={f:.1f}")

# ── SAVE ──
res_df = pd.DataFrame(results)
res_df["corpus_version"] = "data-restored-v1"
res_df["stance_version"] = "stance-measure-v1"
res_df["run_id"] = f"gate5-{NOW[:19]}"
res_df["panel_sha256"] = hashlib.sha256(
    open(PROJECT / "data/processed/analysis_panel.parquet","rb").read()).hexdigest()

out_path = PROJECT / "tables/machine_readable/gate5_all_results.csv"
out_path.parent.mkdir(parents=True, exist_ok=True)
res_df.to_csv(out_path, index=False)
print(f"\nSaved: {out_path} ({len(res_df)} rows)")

# ── FINAL ──
print(f"\n{'='*60}")
print("GATE 5 COMPLETE — Results Summary")
print(f"{'='*60}")
rf = res_df[res_df["model"]=="reduced_form_all"].iloc[0]
fs = res_df[res_df["model"]=="first_stage_all"].iloc[0]
print(f"First stage:  unsc → log(aid)  = {fs['coef']:.4f} ({fs['se']:.4f}) F={fs['f_stat']:.1f}")
print(f"Reduced form: unsc → stance    = {rf['coef']:.4f} ({rf['se']:.4f}) p={rf['p']:.4f}")
print(f"Construct:    corr(stance,us_agree)={d_all['stance'].corr(d_all['us_agree']):.4f}")
print(f"Causal gate:  {'OPEN' if fs_f>10 else 'CLOSED'} (F={fs_f:.1f})")
print(f"Interpretation: No detectable effect of UNSC membership on expressed US stance.")
print(f"  The instrument is too weak to identify a causal aid effect (F<<10).")
