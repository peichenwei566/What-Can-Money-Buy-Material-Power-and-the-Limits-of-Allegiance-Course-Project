# US Stance Scoring Protocol — v2.0 (Target-Attributed)

**Prompt version:** `us_stance_v2`
**Date frozen:** 2026-07-29
**Requirement:** Semantic judgment with mandatory target attribution. Keyword counting alone is insufficient.

## Primary construct

"Does the speaker's own government express affective warmth or criticism toward the United States in this speech?"

Scale: -2 (strongly hostile), -1 (mildly critical), 0 (neutral/absent/mixed/insufficient), +1 (mildly warm), +2 (strongly warm/ admiring).

## Target Attribution Gate (MANDATORY — non-zero scores MUST pass ALL 7 checks)

Before assigning any non-zero score, verify:

1. **Evaluative expression exists.** The text contains words that express warmth, criticism, gratitude, condemnation, approval, or disapproval.
2. **Target is explicitly the United States.** "United States", "America", "American", "US", "USA", "Washington" (as metonym for US government) must be the grammatical or logical target of the evaluation.
3. **Speaker attribution verified.** The sentiment is expressed in the speaker's own voice, not attributed to others.
4. **Not quoted third party.** If the evaluation is inside quotation marks or attributed to another actor ("as X has said..."), it does not count unless the speaker explicitly endorses it.
5. **Not historical narration.** Factual descriptions of past events without evaluative language ("In 2003 the US invaded Iraq") are neutral.
6. **Not directed at others.** Sentiment directed at the UN, other countries, international organizations, or "the international community" does not count as US stance.
7. **Evidence span exists.** The evaluative text and the US target must appear in the same sentence or adjacent sentences in a clear target-evaluation relationship.

## Examples of what does NOT count

| Text | Score | Reason |
|---|---|---|
| "We appreciate the work of the Secretary-General." | 0 | Target is UN, not US |
| "We condemn terrorism in all its forms." | 0 | Target is terrorism, not US |
| "We welcome all nations to join." | 0 | Target is all nations, not US |
| "The meeting was held in New York." | 0 | Factual, no evaluation |
| "As some have said, America is an imperialist power." | 0 | Reported speech, not speaker's own view |
| "We are grateful for international cooperation." | 0 | Target is international community, not US |
| "The United States is a permanent member of the Security Council." | 0 | Factual, no evaluation |

## Examples of what DOES count

| Text | Score | Reason |
|---|---|---|
| "We welcome continued cooperation with the United States." | +1 | US is target, warm evaluation |
| "We condemn the unilateral actions of the United States." | -1 | US is target, critical evaluation |
| "The United States remains a beacon of freedom and democracy." | +2 | US is target, strong admiration |
| "American imperialism threatens the sovereignty of all nations." | -2 | US is target, strong condemnation |
| "We thank the American people for their generosity." | +1 | US is target, appreciation |
| "We regret the decision of the United States to withdraw from the agreement." | -1 | US is target, disappointment |

## Scoring guide

### -2: Strongly hostile
The speaker's own government explicitly condemns the United States as an aggressor, imperialist power, or moral threat. Language is accusatory. Must satisfy target attribution gate.

### -1: Mildly critical
The speaker's own government criticizes specific US policies or actions. Tone is skeptical, disappointed, or corrective. Must satisfy target attribution gate.

### 0: Neutral / absent / mixed / insufficient
- No mention of the United States
- US mentioned only factually or ceremonially
- Positive and negative references roughly balance
- Target attribution gate fails for all evaluative expressions
- Evidence insufficient for reliable coding

### +1: Mildly warm
The speaker's own government expresses appreciation, thanks, or mild positive sentiment toward the United States. Must satisfy target attribution gate.

### +2: Strongly warm
The speaker's own government expresses strong admiration, alliance, shared values, or effusive praise for the United States. Must satisfy target attribution gate.

## Output format

```json
{
  "review_id": "...",
  "iso3": "...",
  "year": 2000,
  "direct_us_mention": true,
  "mention_count": 3,
  "target_is_united_states": true,
  "speaker_attribution_verified": true,
  "quoted_third_party": false,
  "affective_warmth": 1,
  "policy_alignment": 0,
  "order_alignment": 0,
  "primary_stance_score": 1,
  "evidence_spans": ["We welcome continued cooperation with the United States on trade."],
  "target_spans": ["the United States"],
  "confidence": 0.85,
  "insufficient_evidence": false,
  "analysis_text_complete": true,
  "corpus_sha256": "...",
  "prompt_version": "us_stance_v2",
  "model_name": "rule_v2_target_attributed",
  "model_parameters": "sentence_level_target_attribution",
  "scored_at": "...",
  "scoring_run_id": "..."
}
```

## Constraints

- `primary_stance_score` == `affective_warmth`
- Non-zero → `evidence_spans` and `target_spans` non-empty
- Non-zero → `target_is_united_states` == true
- `speaker_attribution_verified` == false → score must be 0
- `insufficient_evidence` == true → score must be 0
- Every `evidence_spans` string must appear verbatim in the analysis_text
