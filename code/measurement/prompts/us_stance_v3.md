# US Stance Scoring Protocol — v3.0 (LLM Semantic)

**Prompt version:** `us_stance_v3`
**Engine type:** `llm_semantic` (no keyword/rule fallback)
**Date:** 2026-07-29

## Task

Read the UN General Debate speech below. Determine the speaker government's expressed affective stance toward the United States. Provide a structured JSON response with evidence.

## Primary construct

Affective warmth or criticism expressed by the speaker's own government toward the United States.

Scale: -2 (strongly hostile), -1 (mildly critical), 0 (neutral/mixed/insufficient/absent), +1 (mildly warm), +2 (strongly admiring).

## Target Attribution (MANDATORY for non-zero)

Before assigning any non-zero score, confirm:
1. An evaluative expression exists
2. The target is explicitly the United States
3. The evaluation is in the speaker's own voice (not quoted third party)
4. It is not merely factual/historical narration
5. Evidence can be quoted verbatim from the text

## Critical Rules

**Do NOT score:**
- "We appreciate the Secretary-General" → target is UN, not US → 0
- "We condemn terrorism" → target is terrorism, not US → 0
- Diplomatic pleasantries, ceremonial greetings → 0
- Third-party quotations → 0 unless speaker endorses
- Generic "international cooperation" → 0 unless US explicitly named as target

**DO score:**
- "We thank the United States for..." → +1 (US is target, gratitude)
- "American imperialism threatens..." → -2 (US is target, condemnation)
- "We welcome continued partnership with Washington" → +1

## Output (STRICT JSON)

```json
{
  "primary_stance_score": 0,
  "affective_warmth": 0,
  "policy_alignment": 0,
  "order_alignment": 0,
  "confidence": 0.85,
  "insufficient_evidence": false,
  "direct_us_mention": true,
  "mention_count": 2,
  "target_is_united_states": true,
  "speaker_attribution_verified": true,
  "quoted_third_party": false,
  "evidence_spans": ["exact quoted text from speech"],
  "target_spans": ["United States"],
  "decision_rationale": "Brief explanation of reasoning"
}
```

## Constraints
- `primary_stance_score` == `affective_warmth`
- Score ∈ {-2, -1, 0, 1, 2}
- Non-zero → `evidence_spans` non-empty AND `target_spans` non-empty
- Non-zero → `target_is_united_states` == true
- Non-zero → `speaker_attribution_verified` == true
- `insufficient_evidence` == true → score == 0
- Every span in `evidence_spans` and `target_spans` must appear verbatim in the speech

## Speech Text
```
{text}
```

Return ONLY the JSON object, no other text.
