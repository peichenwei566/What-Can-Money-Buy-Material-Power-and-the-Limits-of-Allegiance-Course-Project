# Speech Restoration Report — Gate 3

## Source

- **Corpus**: jradius/un-general-debates (GitHub mirror of UN General Debate Corpus)
- **Coverage**: 1946-2022, 21,139 TXT files under `data/original/external/ungdc/`
- **Naming convention**: `ISO3_SESSION_YEAR.txt` (e.g. `USA_75_2020.txt`)
- **Dataverse DOI** (canonical): `doi:10.7910/DVN/0TJX8Y` v14 (blocked by guestbook)
- **Inventory snapshot**: `manifests/original_data_snapshots/20260729T104834Z_ungdc-github-mirror-2024.json`

## Restoration summary

| Metric | Value |
|---|---|
| Total speeches | 7,866 |
| Never truncated | 4,102 |
| Truncated → restored | 3,764 |
| exact-prefix matches | 3,607 |
| normalized-prefix matches | 157 |
| Ambiguous (multiple candidates) | 0 |
| Missing (no candidate found) | 0 |
| Manual review required | 0 |
| `analysis_text_complete` | 7,866 / 7,866 (100%) |

## Length distribution

| Measure | Before (truncated) | After (restored) |
|---|---|---|
| Min chars | 16,000 | 16,002 |
| Median chars | 16,000 | 21,848 |
| Max chars | 16,000 | 72,041 |

All 3,764 restored speeches have `text_full > text_provided` — zero regressions.

## Restoration by era

| Era | Restored count |
|---|---|
| 1970s | 1,111 |
| 1980s | 1,169 |
| 1990s | 972 |
| 2000s | 196 |
| 2010s | 316 |

## Spot-check results

3 samples verified across eras (Albania 1975, Afghanistan 1995, Argentina 2015):
- All exact-prefix matches
- Continuation text is natural diplomatic prose
- Country/year metadata consistent

## Output files

- `data/processed/speeches_full.parquet` — DVC-tracked, 7,866 rows with `text_provided`, `text_full`, `analysis_text`
- `manifests/speech_restoration.jsonl` — per-speech restoration manifest
- `data/interim/manual_review_queue.csv` — empty (0 cases)
- `data/interim/restoration_inventory.parquet` — pre-restoration inventory

## Builder

- Script: `code/restoration/build_restored_corpus.py` (from skill)
- Policy: exact-prefix or normalized-prefix only; all other cases → manual review
- Zero overwrites of original data
