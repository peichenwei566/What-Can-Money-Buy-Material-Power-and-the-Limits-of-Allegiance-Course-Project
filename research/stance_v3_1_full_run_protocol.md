# v3.1 Full Run Protocol — Frozen BEFORE Scoring

**Date:** 2026-07-29
**Tag:** stance-measure-v3_1-protocol-frozen

## Engine

- provider: deepseek
- model: deepseek-v4-pro
- scoring_engine_type: llm_semantic
- temperature: 0 (deterministic)
- max_retries: 2 per record
- batch_size: 33
- concurrency: 3 (Hermes max)
- seed: 20260729

## Retry rule

1. First failure → retry once with same prompt
2. Second failure → log error, mark as failed, do NOT substitute with 0 or keyword score
3. Failed records saved to error queue for manual review

## No fallback

Keyword, regex, dictionary, or rule-based scores are STRICTLY prohibited as primary_stance_score or affective_warmth. They may only be used for mention_count and direct_us_mention.

## Input

- Corpus: data/processed/speeches_full.parquet
- Text column: analysis_text
- Expected rows: 7,866
- Corpus SHA-256: (computed at freeze time)

## Output

- data/processed/speech_stance_scores_v3_1.parquet
- logs/measurement/v3_1_full/raw/
- logs/measurement/v3_1_full/errors/

## QC Gates

All must pass before blind sample generation:
1. 7,866 records
2. 100% schema valid
3. 100% llm_semantic engine type
4. 0 rule fallbacks
5. 100% evidence span verbatim
6. 100% target span verbatim (non-zero)
7. 100% offsets computed
8. 100% non-zero target attribution
9. 0 unresolved LLM failures

## Prompt

code/measurement/prompts/us_stance_v3_1.md
SHA-256: (computed at freeze time)
