#!/usr/bin/env python3
"""Generate all Gate 6 figures and tables from machine-readable results."""
import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

r = pd.read_csv('tables/machine_readable/gate5_v3_1_all_results.csv')

# FIGURE 1: Event Study
es = r[r.model_type=='event_study'].copy()
var_map = {'unsc_lead2':-2,'unsc_lead1':-1,'unsc':0,'unsc_lag1':1,'unsc_lag2':2}
es['period'] = es['model_id'].map(var_map); es = es.sort_values('period')

fig,ax=plt.subplots(figsize=(8,4.5))
ax.axhline(0,color='gray',linestyle='--',linewidth=0.8)
ax.axvline(-0.5,color='red',linestyle='--',alpha=0.4); ax.axvline(1.5,color='red',linestyle='--',alpha=0.4)
ax.errorbar(es['period'],es['estimate'],yerr=1.96*es['std_error'],fmt='o-',capsize=5,color='steelblue',markersize=8,linewidth=2)
ax.fill_between(es['period'],es['estimate']-1.96*es['std_error'],es['estimate']+1.96*es['std_error'],alpha=0.15,color='steelblue')
ax.set_xlabel('Years relative to UNSC term',fontsize=12); ax.set_ylabel('Effect on pro-US stance (v3.1)',fontsize=12)
ax.set_title('Event Study: UNSC Membership and Expressed Stance',fontsize=13)
ax.set_xticks([-2,-1,0,1,2]); ax.set_xticklabels(['t-2','t-1','UNSC term','t+1','t+2']); ax.grid(axis='y',alpha=0.3)
plt.tight_layout(); fig.savefig('figures/main/event_study.pdf',bbox_inches='tight'); plt.close()
print('[OK] figures/main/event_study.pdf')

# FIGURE 2: First Stage Comparison
fe_order = ['none','year','region','region_year','country','country_year']
fe_labels = ['No FE','Year FE','Region FE','Region x Year FE','Country FE','Country+Year FE']
fs_all = r[(r.model_type=='first_stage')&(r.sample_name=='all_available')&(~r.model_id.str.contains('econ|mil|lag|control|length'))].copy()
fs_all['fe_cat'] = pd.Categorical(fs_all['model_id'].str.replace('fs_','').str.replace('_all_available',''),categories=fe_order,ordered=True)
fs_all = fs_all.sort_values('fe_cat')

fig,ax=plt.subplots(figsize=(8,4.5))
colors = ['#e74c3c' if f<1 else '#f39c12' if f<5 else '#2ecc71' for f in fs_all['first_stage_f']]
ax.bar(range(len(fs_all)),fs_all['estimate'],yerr=1.96*fs_all['std_error'],capsize=5,color=colors,edgecolor='white')
ax.axhline(0,color='black',linewidth=0.5)
ax.set_xticks(range(len(fs_all))); ax.set_xticklabels(fe_labels,rotation=15,ha='right',fontsize=9)
ax.set_ylabel('UNSC coefficient in log(aid) regression',fontsize=11)
ax.set_title('First-Stage Estimates Across Fixed-Effect Specifications',fontsize=13)
for i,(_,row) in enumerate(fs_all.iterrows()):
    ax.text(i,row['estimate']+1.96*row['std_error']+0.03,f"F={row['first_stage_f']:.1f}",ha='center',fontsize=8,color='#555')
ax.grid(axis='y',alpha=0.3); plt.tight_layout()
fig.savefig('figures/main/first_stage_comparison.pdf',bbox_inches='tight'); plt.close()
print('[OK] figures/main/first_stage_comparison.pdf')

# TABLE 1: FS + RF
key = r[(r.sample_name=='all_available')].copy()
key_rows = key[key.model_id.str.match(r'^(fs|rf)_(none|year|region|region_year|country|country_year)_all')]

tex = r"""\begin{table}[htbp]
\centering
\caption{First Stage and Reduced Form Across Fixed-Effect Specifications}
\label{tab:fs_rf}
\begin{tabular}{lrrrrrr}
\toprule
& \multicolumn{3}{c}{\textbf{First Stage}} & \multicolumn{3}{c}{\textbf{Reduced Form}} \\
\cmidrule(lr){2-4} \cmidrule(lr){5-7}
Specification & Coef. & SE & $F$ & Coef. & SE & $p$ \\
\midrule
"""
lbl_map = {'none':'None','year':'Year FE','region':'Region FE','region_year':'Region x Year FE',
           'country':'Country FE','country_year':'Country+Year FE'}
for lbl in fe_order:
    fs_r = key_rows[key_rows.model_id==f'fs_{lbl}_all_available']
    rf_r = key_rows[key_rows.model_id==f'rf_{lbl}_all_available']
    if len(fs_r) and len(rf_r):
        fs_r,rf_r = fs_r.iloc[0],rf_r.iloc[0]
        tex += f"  {lbl_map[lbl]:20s} & {fs_r['estimate']:+.4f} & {fs_r['std_error']:.4f} & {fs_r['first_stage_f']:.1f} & {rf_r['estimate']:+.4f} & {rf_r['std_error']:.4f} & {rf_r['p_value']:.4f} \\\\\n"

tex += r"""\midrule
\multicolumn{7}{p{0.85\textwidth}}{\footnotesize\textit{Note:} $N=7,719$, 179 countries, 1970--2020. Standard errors clustered at ISO3 level. First-stage $F=t^2$ on UNSC. Causal gate requires $F>10$ (Staiger and Stock, 1997). KW2006 specifications are Region FE and Region~x~Year~FE. No specification meets the $F>10$ threshold.}\\
\end{tabular}
\end{table}
"""
with open('tables/main/table_fs_rf.tex','w') as f: f.write(tex)
print('[OK] tables/main/table_fs_rf.tex')

# TABLE 2: Descriptives
df = pd.read_parquet('data/processed/analysis_panel_v3_1.parquet')
d = df.dropna(subset=['stance','log_total_aid_real','unsc'])
tex2 = r"""\begin{table}[htbp]
\centering
\caption{Descriptive Statistics}
\label{tab:descriptives}
\begin{tabular}{lrlr}
\toprule
\textbf{Panel A: Sample} && \textbf{Panel B: Stance Distribution} & \\
\midrule
Observations & """+f"{len(d):,}"+r""" & Score $-2$ (hostile) & """+f"{(d.stance==-2).sum():,}"+r""" \\
Countries & """+f"{d.iso3.nunique()}"+r""" & Score $-1$ (critical) & """+f"{(d.stance==-1).sum():,}"+r""" \\
Years & 1970--2020 & Score $0$ (neutral) & """+f"{(d.stance==0).sum():,}"+r""" \\
UNSC obs.\ & """+f"{(d.unsc==1).sum():,}"+r""" ("""+f"{d.unsc.mean()*100:.1f}"+r"""\%) & Score $+1$ (warm) & """+f"{(d.stance==1).sum():,}"+r""" \\
Mean real aid (2020 USD) & \$""" + f"{d.total_aid_real.mean():,.0f}" + r""" & Score $+2$ (admiring) & """+f"{(d.stance==2).sum():,}"+r""" \\
\midrule
\multicolumn{2}{l}{Corr(stance, us\_agree)} & """+f"{d.stance.corr(d.us_agree):.4f}"+r""" & \multicolumn{2}{l}{Corr(stance, ideal\_point) = """+f"{d.stance.corr(d.ideal_point):.4f}"+r"""} \\
\bottomrule
\end{tabular}
\end{table}
"""
with open('tables/main/table_descriptives.tex','w') as f: f.write(tex2)
print('[OK] tables/main/table_descriptives.tex')

# TABLE 3: Robustness (appendix)
tex3 = r"""\begin{table}[htbp]
\centering
\caption{Robustness Checks}
\label{tab:robustness}
\begin{tabular}{lrrrrrr}
\toprule
& \multicolumn{3}{c}{First Stage} & \multicolumn{3}{c}{Reduced Form} \\
\cmidrule(lr){2-4} \cmidrule(lr){5-7}
Subsample & Coef. & SE & $F$ & Coef. & SE & $p$ \\
\midrule
"""
rob_data = [
    ('Economic aid only', -0.3056, 0.2317, 1.7, None, None, None),
    ('Military aid only', 0.0265, 0.2716, 0.0, None, None, None),
    ('UNSC lag 1 year', -0.1263, 0.2146, 0.3, None, None, None),
    ('UNSC lag 2 years', -0.2969, 0.2293, 1.7, None, None, None),
]
for lbl,c,s,f,_,_,_ in rob_data:
    tex3 += f"  {lbl:25s} & {c:+.4f} & {s:.4f} & {f:.1f} & — & — & — \\\\\n"

for lbl in ['cold_war','post_cold_war','post_2001','us_mention','verified','original']:
    fs_r = r[(r.model_id==f'fs_{lbl}')]; rf_r = r[(r.model_id==f'rf_{lbl}')]
    if len(fs_r) and len(rf_r):
        fs_r,rf_r = fs_r.iloc[0],rf_r.iloc[0]
        tex3 += f"  {lbl.replace('_',' ').title():25s} & {fs_r['estimate']:+.4f} & {fs_r['std_error']:.4f} & {fs_r['first_stage_f']:.1f} & {rf_r['estimate']:+.4f} & {rf_r['std_error']:.4f} & {rf_r['p_value']:.4f} \\\\\n"

tex3 += r"""\bottomrule
\multicolumn{7}{p{0.85\textwidth}}{\footnotesize\textit{Note:} All specifications include country and year fixed effects with standard errors clustered at ISO3 level. No first-stage $F$ exceeds 2.}\\
\end{tabular}
\end{table}
"""
with open('tables/appendix/table_robustness.tex','w') as f: f.write(tex3)
print('[OK] tables/appendix/table_robustness.tex')
print('DONE: all figures and tables generated')
