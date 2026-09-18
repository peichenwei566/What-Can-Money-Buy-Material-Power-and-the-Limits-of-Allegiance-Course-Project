#!/usr/bin/env python3
"""Fail if a public release contains restricted or row-level research data."""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "tables/machine_readable/gate5_v3_1_all_results.csv"

FORBIDDEN_TOP_LEVEL = {"data", "inputs", "outputs", "logs", "interaction", "private", "restricted"}
FORBIDDEN_SUFFIXES = {
    ".parquet", ".dta", ".sav", ".feather", ".arrow", ".xlsx", ".xls", ".jsonl", ".zip", ".tar"
}
FORBIDDEN_NAME_PARTS = {
    "blinded_stance_validation",
    "speech_stance_scores",
    "analysis_panel",
    "compact_batch",
}
SENSITIVE_CSV_FIELDS = {
    "text", "analysis_text", "speech_text", "evidence_spans", "target_spans", "decision_rationale"
}
SECRET_PATTERN = re.compile(r"(?:sk-[A-Za-z0-9_-]{12,}|api[_-]?key\s*[:=]|password\s*[:=])", re.I)
LOCAL_PATH_PATTERN = re.compile(r"(?:/" + r"Users/|[A-Za-z]:\\\\" + r"Users\\\\)")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]
    violations: list[str] = []

    for path in files:
        rel = path.relative_to(ROOT)
        rel_lower = rel.as_posix().lower()
        if rel.parts and rel.parts[0].lower() in FORBIDDEN_TOP_LEVEL:
            violations.append(f"restricted directory: {rel}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or rel_lower.endswith(".tar.gz"):
            violations.append(f"restricted file type: {rel}")
        if any(part in rel_lower for part in FORBIDDEN_NAME_PARTS):
            violations.append(f"restricted filename: {rel}")
        if path.stat().st_size > 10 * 1024 * 1024:
            violations.append(f"unexpected file over 10 MiB: {rel}")

        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                fields = set(next(csv.reader(handle), []))
            leaked = fields & SENSITIVE_CSV_FIELDS
            if leaked:
                violations.append(f"row-level text fields {sorted(leaked)}: {rel}")

        if path.suffix.lower() in {".py", ".md", ".yml", ".yaml", ".json", ".tex", ".cff"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if SECRET_PATTERN.search(text):
                violations.append(f"possible credential: {rel}")
            if LOCAL_PATH_PATTERN.search(text):
                violations.append(f"local user path: {rel}")

    require(not violations, "Public-release audit failed:\n  " + "\n  ".join(sorted(set(violations))))
    require(RESULTS.is_file(), "Missing aggregate model results")

    with RESULTS.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 72, f"Expected 72 aggregate estimates, found {len(rows)}")
    by_id = {row["model_id"]: row for row in rows}
    fs = by_id["fs_country_year_all_available"]
    rf = by_id["rf_country_year_all_available"]
    require(abs(float(fs["first_stage_f"]) - 0.0764644708773738) < 1e-10, "First-stage F changed")
    require(abs(float(rf["estimate"]) + 0.0996119093339506) < 1e-10, "Reduced-form estimate changed")
    require((ROOT / "paper/build/main.pdf").is_file(), "Missing release paper")

    print("Public-release validation passed")
    print(f"  audited files: {len(files)}")
    print("  restricted data files: 0")
    print(f"  aggregate estimates: {len(rows)}")


if __name__ == "__main__":
    main()
