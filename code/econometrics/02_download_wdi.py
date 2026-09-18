#!/usr/bin/env python3
"""Download WDI controls fast: batch country codes, save incrementally."""
import json, time, urllib.request, sys
from pathlib import Path
import pandas as pd

PROJECT = Path(__file__).resolve().parents[2]
CACHE = PROJECT / "data/interim/wdi_controls_v2.parquet"

# Load existing progress
if CACHE.exists():
    wdi = pd.read_parquet(CACHE)
    done_iso3 = set(wdi["iso3"].unique())
    print(f"Resuming: {len(wdi)} rows, {len(done_iso3)} countries cached")
else:
    wdi = None
    done_iso3 = set()

panel = pd.read_csv(PROJECT / "data/original/course_package/country_year_panel.csv")
P5 = {"USA","GBR","FRA","RUS","CHN"}
iso3_list = sorted(panel[~panel["iso3"].isin(P5) & (panel["iso3"] != ".")]["iso3"].unique())
todo = [i for i in iso3_list if i not in done_iso3]
print(f"Countries: {len(iso3_list)} total, {len(done_iso3)} cached, {len(todo)} to fetch")

INDICATORS = {
    "NY.GDP.PCAP.KD": "gdp_pc_2015usd",
    "SP.POP.TOTL":    "population",
    "NE.TRD.GNFS.ZS": "trade_pct_gdp",
}

BATCH_SIZE = 20  # countries per API call
all_new = []
for batch_start in range(0, len(todo), BATCH_SIZE):
    batch = todo[batch_start:batch_start + BATCH_SIZE]
    countries = ";".join(batch)

    for code, name in INDICATORS.items():
        url = (
            f"https://api.worldbank.org/v2/country/{countries}/indicator/{code}"
            f"?format=json&per_page=3000&date=1970:2020&source=2"
        )
        req = urllib.request.Request(url, headers={
            "User-Agent": "Project3/1.0", "Accept": "application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as f:
                resp = json.load(f)
            if resp and len(resp) > 1 and resp[1]:
                for d in resp[1]:
                    if d["value"] is not None and d.get("countryiso3code"):
                        iso3 = d["countryiso3code"]
                        all_new.append({
                            "iso3": iso3, "year": int(d["date"]),
                            "indicator": name, "value": float(d["value"])
                        })
        except Exception as e:
            print(f"  FAIL {countries[:30]}... / {name}: {e}")

    print(f"  [{batch_start+len(batch)}/{len(todo)}] batch done")
    time.sleep(0.3)

# Combine and save
new_df = pd.DataFrame(all_new)
if wdi is not None:
    wdi = pd.concat([wdi, new_df], ignore_index=True)
else:
    wdi = new_df

wdi.to_parquet(CACHE)

# Report
wdi_wide = wdi.pivot_table(index=["iso3","year"], columns="indicator", values="value").reset_index()
print(f"\nSaved: {len(wdi)} rows")
for col in INDICATORS.values():
    if col in wdi_wide.columns:
        nn = wdi_wide[col].notna().sum()
        print(f"  {col}: {nn:,} non-null")
print(f"  Total: {len(wdi_wide)} panel rows, {wdi_wide.iso3.nunique()} countries")
