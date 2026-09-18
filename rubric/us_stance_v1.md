# US Stance Scoring Protocol — v1.0

**Prompt version:** `us_stance_v1`
**Date frozen:** 2026-07-29
**Model requirement:** Any instruction-tuned LLM capable of structured JSON output.

## Task

You are scoring a country's annual address to the United Nations General Debate. Your task is to read the speech and assess the country's expressed affective stance toward the United States.

## Output format

Return ONLY a valid JSON object with these fields:

```json
{
  "direct_us_mention": true,
  "mention_count": 3,
  "primary_stance_score": 1,
  "affective_warmth": 1,
  "policy_alignment": 0,
  "order_alignment": 1,
  "confidence": "high",
  "insufficient_evidence": false,
  "evidence_spans": [
    {
      "score": 1,
      "text": "We thank the United States for its continued partnership in fighting terrorism.",
      "explanation": "Expresses gratitude and describes the US as a partner — warm but not effusive."
    }
  ]
}
```

## Field definitions

### direct_us_mention (boolean)
True if the speech mentions "United States," "America," "American," "US," "USA," "Washington" (as metonym for US government), or an explicit reference to a named US president/administration in the context of US policy.

### mention_count (integer)
Number of distinct passages referring to the United States. Count paragraphs or distinct topical blocks, not individual word occurrences.

### primary_stance_score (integer, -2 to +2)
The overall affective stance toward the United States. This is `affective_warmth` but must be the single best summary score. See scoring guide below.

### affective_warmth (integer, -2 to +2)
The expressed emotional warmth or hostility toward the United States as an actor.

### policy_alignment (integer, -2 to +2)
Agreement with specific US policies mentioned in the speech. Independent of affective warmth.

### order_alignment (integer, -2 to +2)
Support for the US-led international institutional order (UN, Bretton Woods, NATO, democratic norms framed as Western). Independent of affect.

### confidence (string: "high", "medium", "low")
How confident you are in the primary_stance_score.
- **high:** Clear, unambiguous evaluative language; multiple consistent references.
- **medium:** Some evaluative language but mixed signals or single brief reference.
- **low:** Marginal, ambiguous, or heavily context-dependent.

### insufficient_evidence (boolean)
True if the speech contains NO content that allows reliable coding of US stance. This includes:
- The US is never mentioned or referenced.
- The only references are purely factual (e.g., "The United States is a member of the Security Council") with no evaluative content.
- The text is too garbled, truncated, or otherwise uninterpretable.

### evidence_spans (array of objects)
For each piece of evidence supporting your score, provide:
- `score`: the contribution of this span (-2 to +2)
- `text`: exact quoted text from the speech (up to 300 chars)
- `explanation`: why this text supports the score

Include at least 1 span if `insufficient_evidence` is false. Include spans for mixed signals (both positive and negative evidence).

## Scoring guide for affective_warmth

### Score -2 (Strongly critical / hostile)
The speech condemns the United States using language such as:
- "imperialist," "aggressor," "hegemonic," "oppressor," "criminal"
- The US is blamed for wars, exploitation, global inequality, human rights violations
- Calls for resistance against US actions or policies
- The US is described as a threat to the speaker's country or to world peace

Examples:
- "The imperialist aggression of the United States threatens the sovereignty of nations."
- "American hegemony is the root cause of instability in our region."

### Score -1 (Mildly critical / skeptical)
The speech criticizes specific US policies or actions with measured language:
- Disagreement with a specific US position or policy
- Calls for the US to change course
- Skepticism about US motives or commitments
- Distancing from US actions while not condemning the US as an actor

Examples:
- "We call on the United States to reconsider its approach to climate negotiations."
- "The American embargo has caused hardship, and we urge its lifting."

### Score 0 (Neutral / balanced / absent)
- The US is not mentioned at all
- The US is mentioned only in factual/descriptive contexts
- Positive and negative references approximately balance
- Unclear or ambiguous stance
- Reference to the US only as venue (e.g., "The meeting was held in New York")

Examples:
- "We note the statement made by the representative of the United States."
- "The United States is a permanent member of the Security Council."

### Score +1 (Mildly warm / appreciative)
The speech expresses appreciation or mild positive sentiment:
- Thanks for specific US assistance, cooperation, or support
- Recognition of positive US contributions or efforts
- Expression of desire for continued or improved relations
- Describing the US as a "partner," "friend," or "ally" in specific contexts

Examples:
- "We appreciate the development assistance provided by the United States."
- "We look forward to strengthening our cooperation with Washington on trade."

### Score +2 (Strongly warm / admiring)
The speech expresses strong alignment, admiration, or effusive praise:
- The US is described as a leader, moral exemplar, indispensable nation
- Strong statements of shared values, common destiny, or deep friendship
- Enthusiastic endorsement of US global leadership
- The US is defended against its critics

Examples:
- "The United States remains the indispensable nation, a beacon of freedom admired by all."
- "Our friendship with the American people is unshakeable and eternal."

## Critical rules

1. **Be conservative on insufficient evidence.** If the speech mentions the US only in passing or without any evaluative content, set `insufficient_evidence: true` and `primary_stance_score: 0`.

2. **Distinguish policy from affect.** A country can disagree with a US policy (-1 policy_alignment) while expressing warmth toward the US (+1 affect). Code each dimension independently.

3. **Quote the speech.** Every evidence span must contain an exact text excerpt from the speech.

4. **Report mixed signals.** If the speech contains both positive and negative references, include evidence spans for both and score the net affect. A speech that criticizes US climate policy (-1) but thanks the US for security cooperation (+1) might net to 0 or a slight lean depending on emphasis.

5. **No external knowledge.** Score based only on the text provided. Do not use your knowledge of current events, bilateral relations, or aid flows.

## Speech text

```
{text}
```
