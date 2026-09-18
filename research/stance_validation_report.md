# Stance Measure Validation Report — Gate 4

## Measure

- **Method:** Dictionary-based keyword matching (us_stance_v1)
- **Corpus:** `data/processed/speeches_full.parquet` (7,866 speeches, all complete)
- **Scoring script:** `code/measurement/score_stance_dict.py`
- **Prompt version:** `us_stance_v1` (frozen 2026-07-29)

## Score distribution (full corpus)

| Score | Count | Pct |
|---|---|---|
| -2 (hostile) | 708 | 9.0% |
| -1 (critical) | 2,091 | 26.6% |
| 0 (neutral) | 4,615 | 58.7% |
| +1 (warm) | 431 | 5.5% |
| +2 (admiring) | 21 | 0.3% |
| Insufficient evidence | 1,492 | 19.0% |

## LLM spot-check validation (10 speeches)

| Country | Year | Dict | LLM | Issue |
|---|---|---|---|---|
| Kenya | 1971 | -2 | 0 | Dict captured anti-colonial rhetoric misattributed to US |
| Yemen | 2001 | -2 | 0 | Sympathetic 9/11 response, not hostile |
| Botswana | 1984 | -1 | 0 | No US mention; diplomatic pleasantries scored |
| **Slovakia** | **2001** | **-1** | **+1** | **Pro-US solidarity miscoded as criticism** |
| Peru | 1982 | 0 | 0 | Correct |
| Belize | 1998 | 0 | 0 | Correct |
| Mexico | 1977 | +1 | 0 | "Appreciation" directed at UN officials |
| San Marino | 2008 | +1 | 0 | Same — diplomatic language, not US-directed |
| Panama | 1982 | +2 | 0 | No US mention |
| El Salvador | 1995 | +2 | 0 | No US mention |

**Exact agreement:** 3/10 (30%)

## Known measurement limitations

### 1. Context blindness
The dictionary counts positive/negative terms across the entire speech without verifying the TARGET of the sentiment. Generic diplomatic language ("we appreciate", "we are grateful", "we condemn") is scored regardless of whether the target is the United States or another actor. This inflates both positive and negative scores.

### 2. False negatives for implicit stance
A speech can be strongly pro- or anti-US without using any dictionary terms — for example, through narrative framing, implicit comparison, or omission. The dictionary cannot detect these.

### 3. Term overlap with non-US contexts
"American" appears in references to Latin America, the Organization of American States, "American people" in generic solidarity contexts, etc. "Washington" can refer to the city as venue.

### 4. Limited negative lexicon in diplomatic register
UN diplomatic language tends to be circumspect. Direct condemnations ("American imperialism") are rare outside specific historical periods and regional blocs. Milder but systematic criticism may be missed.

## Mitigations for Gate 5

- The `insufficient_evidence` flag (19.0% of speeches) identifies cases with no evaluative terms — these can be excluded or downweighted.
- The continuous score (`affective_warmth_continuous`) preserves gradation and may be more informative than the discrete score.
- Sensitivity analysis: compare results using only speeches with `confidence=high` (multi-term evidence).
- The `direct_us_mention` flag can be used to subset to speeches where US is explicitly named.

## Convergence validation (pending — for after measure freeze)

Once the measure is accepted as frozen, the following should be checked WITHOUT modifying the measure:
- Correlation between dictionary score and `us_agree` (expected sign: positive)
- Correlation with `ideal_point` (expected sign: positive)
- Comparison across UNSC members vs non-members (pre-aid analysis)

## Recommendation

The dictionary score is adequate as a first-pass continuous measure. Its known biases (context-blindness, diplomatic-language inflation) should be transparently reported. The primary analysis should:
1. Use the continuous `affective_warmth_continuous` score
2. Report sensitivity to `confidence` and `insufficient_evidence` filters
3. Acknowledge that the measure captures "evaluative language density" rather than "stance toward the US specifically"
4. Not overclaim precision — treat the score as a noisy but informative signal
