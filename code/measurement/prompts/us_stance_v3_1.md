# US Stance Scoring Protocol — v3.1 (LLM Semantic, Auditable Target Grounding)

**Prompt version:** `us_stance_v3_1`
**Engine type:** `llm_semantic` (no keyword/rule fallback)
**Date:** 2026-07-29
**Changes from v3:** Target grounding rules only (see change log).

## Task

Read the UN General Debate speech. Determine the speaker government's expressed affective stance toward the United States. Provide structured JSON with verbatim evidence.

## Primary construct

Affective warmth or criticism expressed by the speaker's own government toward the United States.

Scale: -2 (strongly hostile), -1 (mildly critical), 0 (neutral/mixed/insufficient), +1 (mildly warm), +2 (strongly admiring).

## CRITICAL: Target Span Rules (v3.1)

1. **Every target_span MUST be copied verbatim from the speech text below.** Do NOT rewrite, normalize, or paraphrase.
2. **Strip leading/trailing whitespace.** "United States" not " United States ".
3. **No ellipsis (…).** Always output the complete fragment.
4. **target_spans must identify the evaluation target.** Return the shortest complete fragment that identifies the United States as the target.
5. **Pronouns require antecedents.** If using "it" or "that country" to refer to the US, also include the fragment with the explicit "United States" reference.
6. **"West"/"Western powers"/"NATO"** only valid when context explicitly links them to the US.
7. **Each target_span must appear verbatim** in the speech text below.
8. **Non-zero score → target_spans non-empty.** If no verbatim target can be provided, score=0.

## Previous rules (unchanged from v3)

- Score ∈ {-2, -1, 0, 1, 2}
- primary_stance_score == affective_warmth
- Non-zero → evidence_spans non-empty AND target_spans non-empty
- Non-zero → target_is_united_states == true
- Non-zero → speaker_attribution_verified == true
- insufficient_evidence == true → score == 0
- Diplomatic pleasantries NOT directed at US → 0
- Third-party quotations → 0 unless speaker endorses

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
  "evidence_spans": ["exact verbatim quote from speech"],
  "target_spans": ["United States"],
  "decision_rationale": "Brief explanation"
}
```

Target spans MUST be exact substrings of the speech text. The validator will strip whitespace and normalize Unicode (NFKC) before comparing, but do not rely on this — output clean verbatim fragments.

Return ONLY the JSON object.

## Speech Text
```
{text}
```
