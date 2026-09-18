# Stance Construct Definition — Gate 4

## Primary construct: Affective warmth/criticism toward the United States

**Definition:** The degree of expressed affective warmth, admiration, respect, or conversely hostility, criticism, and condemnation directed at the United States *as an actor* in a country's UN General Debate address.

The construct captures emotional tone and evaluative stance — how a country *feels* about the US based on its words. It is orthogonal to whether the country agrees with specific US policies or participates in US-led institutions.

**Scale:** Integer scores from -2 to +2.

| Score | Label | Description |
|---|---|---|
| -2 | Strongly critical / hostile | The US is condemned as an aggressor, imperialist power, source of global instability, or moral threat. Language is accusatory, denunciatory. |
| -1 | Mildly critical / skeptical | The US is criticized for specific policies or actions. Tone is skeptical, disappointed, or corrective but not denunciatory. |
| 0 | Neutral / balanced / absent | No detectable affective stance toward the US; or positive and negative references balance out; or the US is mentioned only factually; or the US is not mentioned at all. |
| +1 | Mildly warm / appreciative | The US is praised for specific actions, thanked for cooperation, or described in positive terms. Tone is welcoming, appreciative. |
| +2 | Strongly warm / admiring | The US is described as a friend, partner, leader, or moral exemplar. Language conveys alliance, shared values, admiration, or deep gratitude. |

## What this construct IS

- **Affective/emotional stance:** warmth, hostility, admiration, contempt *expressed toward the US as a referent*.
- **Directed at the US:** statements about "the United States," "Washington," "the American people," "the US government," etc.
- **Grounded in the speaker's own voice:** the country's own expressed sentiment, not reported speech about what others think.
- **Coded from the speech text alone:** no external knowledge of US relations with the country.

## What this construct IS NOT

- **Policy agreement:** a country can disagree with US policies while speaking warmly (e.g., "We value our friendship with the American people even as we disagree on trade policy"). Scored separately as `policy_alignment`.
- **Institutional order alignment:** a country can support UN-based multilateralism without warmth toward the US. Scored separately as `order_alignment`.
- **Mention frequency:** how often the US is named. High mention count does not imply positive or negative stance.
- **Alliance membership:** formal alliance status is not the same as expressed warmth.
- **Strategic interest:** the country may have strategic reasons for its expressed stance; the construct measures expression, not sincerity.

## Secondary dimensions

### Policy alignment (−2 to +2)
Agreement with specific US policy positions mentioned in the speech: trade, climate, security, regional conflicts. Coded independently of affective tone.

### Order alignment (−2 to +2)
Support for or identification with the US-led international institutional order: UN system, Bretton Woods institutions, NATO, democratic norms framed as Western/American. Coded independently.

## Edge cases and rules

### Quotation and reported speech
- If the speaker quotes another actor's criticism of the US, this is NOT scored as the speaker's own stance unless the speaker endorses it.
- "As some have said, American imperialism..." → not scored. "We agree that American imperialism..." → scored.

### Historical narration
- Factual descriptions of past US actions without evaluative language → neutral (0).
- "In 2003 the United States invaded Iraq" (factual) vs "In 2003 the United States illegally invaded Iraq" (critical, -1) vs "the criminal US invasion of Iraq" (-2).

### Irony and sarcasm
- Apparent praise that is clearly ironic → score the intended meaning. Flag as ironic in evidence.

### Third-party criticism
- Criticism of a third party that the US also opposes is not warmth toward the US unless the speaker explicitly aligns with the US.

### Indirect US references
- "Western powers," "the West," "certain permanent members," "major powers" without naming the US → note in evidence but unless the US is clearly the referent, do not score as US-directed.
- NATO → flag as `order_alignment`, not primary affect unless US is explicitly named.

### Negation handling
- "The United States is not our enemy" → positive affect (+1) because it refutes hostility.
- "We do not support American aggression" → critical (-1) because it associates the US with aggression.

### No mention
- If the US is not mentioned in the speech, this is coded as `insufficient_evidence` = true and primary score = 0, confidence = low.

## Relationship to validation signals

`us_agree` (voting agreement) and `ideal_point` are reserved as convergent validation signals. They must NOT be used to:
- Select which speeches to score
- Choose between alternative scoring rubrics
- Tune prompt wording or examples
- Set thresholds or calibration parameters

They may be used only after the measure is frozen to report correlation as evidence of convergent validity.
