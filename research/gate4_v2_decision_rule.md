# Gate 4 v2 Decision Rule — Frozen BEFORE Codex comparison

**Date:** 2026-07-29
**Status:** Pre-registered. Must NOT be modified after Codex results are read.

## PASS (ALL conditions must hold)

| # | Condition | Threshold |
|---|---|---|
| 1 | All 200 samples matched | = 200 |
| 2 | Linear weighted Cohen's κ | ≥ 0.60 |
| 3 | Within ±1 agreement | ≥ 85% |
| 4 | Direction conflict rate | ≤ 5% |
| 5 | US target attribution validity (non-zero) | ≥ 95% |
| 6 | Evidence span verbatim verification pass rate | ≥ 95% |
| 7 | No systematic subgroup failure | no single era/region/restoration subgroup with κ < 0.40 AND direction conflict > 10% |
| 8 | Codex blind integrity + QC | all PASS |

## CONDITIONAL (any of these)

| # | Condition |
|---|---|
| C1 | 0.40 ≤ κ < 0.60 |
| C2 | 5% < direction conflict ≤ 10% |
| C3 | Overall acceptable but one major subgroup has κ < 0.35 |

## FAIL (any of these)

| # | Condition |
|---|---|
| F1 | κ < 0.40 |
| F2 | Direction conflict > 10% |
| F3 | Systematic target attribution failure (validity < 90%) |
| F4 | Evidence span verification < 90% |
| F5 | Blind broken (Codex saw Hermes scores, aid, UNSC, or v1 results) |
| F6 | Substantive overlap between v2 validation and v1 diagnostic samples (> 0 samples) |
| F7 | Codex input hash does not match Hermes blinded CSV hash |

## Gate 4 final assessment mapping

- **PASS** → `gate4_ai_substitute_assessment = pass`, tag `stance-measure-v2-ai-validated`
- **CONDITIONAL** → `gate4_ai_substitute_assessment = conditional`, no tag, report sub-groups needing diagnosis
- **FAIL** → `gate4_ai_substitute_assessment = fail`, no Gate 5 with v2
