# v3 → v3.1 Change Log

**Date:** 2026-07-29
**Scope:** Target grounding + auditability only. No semantic threshold changes.

## Changes

1. **target_spans MUST be verbatim.** LLM must copy exact substrings from analysis_text. No trailing/leading spaces. No rewriting.

2. **Whitespace stripping.** Validator strips whitespace from target_spans before comparison. "US " → "US" before check.

3. **Unicode normalization.** Validator applies NFKC normalization to both target_span and analysis_text before comparison.

4. **target_span_offsets added.** Validator computes `start` and `end` character positions for each span using strict `str.find()`.

5. **No ellipsis.** Target spans must not contain "..." — always complete fragments.

6. **Pronoun resolution.** If referring to US with a pronoun ("it", "that country"), must include the antecedent fragment with explicit US mention.

7. **Non-zero → mandatory target.** If no verbatim target span can be provided, score must be 0 with insufficient_evidence=true.

## NOT changed

- Scoring thresholds (-2, -1, 0, +1, +2 boundaries)
- Affective warmth definition
- Target attribution logic (already correct)
- policy_alignment / order_alignment
- confidence thresholds
- insufficient_evidence criteria
- Codex agreement optimization (κ is diagnostic only)

## Purpose

v3.1 only fixes target grounding auditability. It does NOT attempt to increase κ with Codex.
