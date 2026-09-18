# Identification Memo — Project 3

## 1. Core elements

| Element | Definition |
|---|---|
| **Unit** | Country-year (iso3, year), 1970–2020 |
| **Treatment (D)** | `total_aid` = U.S. economic + military assistance obligations (historical US$, USAID Greenbook) |
| **Instrument (Z)** | `unsc` = 1 if country holds a non-permanent UN Security Council seat that year |
| **Outcome (Y)** | Pro-U.S. stance score derived from UN General Debate speech text (to be built in Gate 4) |
| **Target population** | Non-P5 UN member states, 1970–2020 |
| **Estimand** | LATE of U.S. aid on expressed pro-U.S. stance, for countries whose aid receipt is affected by UNSC membership |

## 2. Why aid is endogenous

A naive OLS regression of pro-U.S. speech stance on U.S. aid would suffer from:

- **Reverse causality:** Countries that already speak warmly about the U.S. may attract more aid — the U.S. may reward friendly rhetoric with resources.
- **Omitted variables:** Unobserved time-varying factors (e.g., a pro-Western leader's election, a strategic alliance, shared security threats) drive both aid allocation and diplomatic rhetoric.
- **Strategic allocation:** The U.S. allocates aid to strategically important countries, which may also speak more (or less) warmly about the U.S. for strategic reasons unrelated to aid.
- **Simultaneity:** A country may simultaneously seek aid and signal alignment in speeches as part of a broader diplomatic strategy.

Direction of bias: likely upward (countries receiving more aid tend to be more aligned for reasons beyond the aid itself), but could be downward if aid is directed to "swing" states whose alignment is in question.

## 3. Instrument relevance: UNSC membership and aid

### First-stage evidence

- **Kuziemko and Werker (2006, JPE):** UNSC membership is associated with a ~59% increase in total U.S. aid and a ~168% increase in UN development aid. The effect is concentrated in years when the Council is particularly active on issues relevant to the U.S.
- **Dreher, Sturm, and Vreeland (2009, JDE):** UNSC membership increases the probability of World Bank projects and commitments. The mechanism operates through the U.S.'s influence in multilateral institutions.
- **Sanity check from codebook:** A two-way (country + year) FE regression of `log(1+total_aid)` on `unsc` gives a positive coefficient of approximately +0.09.

### Why UNSC membership matters for aid

UNSC non-permanent seats are allocated by regional rotation with a formal election by the General Assembly. Members serve 2-year terms. The U.S. uses aid to influence votes on the Council because:

1. The Council authorizes peacekeeping, sanctions, and military interventions that directly affect U.S. foreign policy interests.
2. Elections to non-permanent seats are often uncontested within regions, making the rotation quasi-random after conditioning on region.
3. The U.S. has a revealed preference for buying influence on the Council through bilateral aid.

## 4. Exclusion restriction threats

The exclusion restriction requires that UNSC membership affects how a country speaks about the U.S. in UN General Debate speeches *only through* changes in U.S. aid. This is the most fragile part of the design.

### Direct channels (UNSC membership → speech, not through aid)

1. **Status and identity effects:** Sitting on the Security Council may change how a country sees itself and speaks about global powers, independent of aid flows. A non-permanent member may adopt more "responsible" or "great-power-aligned" rhetoric simply because it now participates in Council deliberations.
2. **Agenda exposure:** UNSC membership exposes countries to U.S. diplomatic framing of security issues. This exposure may shift how they talk about the U.S. — making references more frequent or differently toned — without any aid transfer.
3. **Rhetorical conformity:** Countries may moderate their General Debate speeches to avoid contradicting positions they have taken (or will take) in Council meetings, where their vote carries more weight. This "consistency channel" operates through diplomatic logic, not aid.
4. **Bureaucratic capacity:** UNSC membership may strain small-state diplomatic capacity, shifting speech content toward great-power issues simply because diplomats are spending more time on them.
5. **Temporal lags:** The 2-year term creates anticipation and legacy effects that are difficult to separate from aid effects: countries may change behavior before the term begins (campaigning) or after it ends (legacy of Council experience).

### Mitigation strategies

- **Region-year fixed effects:** Absorb regional time trends that correlate with both rotation probability and speech content.
- **Event-study specification:** Estimate leads and lags to test for pre-trends and post-term persistence that would be inconsistent with an aid channel.
- **Reduced form:** Report the reduced-form effect of UNSC membership on speech stance directly. This does not require the exclusion restriction and is an important self-standing result.
- **Alternative outcomes:** If aid channel is the mechanism, we should see stronger effects for countries receiving more aid conditional on UNSC membership; if rhetorical conformity is the mechanism, the effect should be present regardless of aid levels.

## 5. Rotation non-randomness

UNSC non-permanent seats are allocated by regional groups with formal elections. Key threats to quasi-randomness:

- **Contested elections:** Some elections are competitive. Countries that win contested elections may differ systematically from those that lose. Accounting for election competitiveness (e.g., split-sample by margin of victory) is important.
- **Strategic candidacy:** Countries self-select into candidacy. Those that run for a seat may be on an upward diplomatic trajectory for reasons correlated with both aid and speech content.
- **Regional heterogeneity:** The rotation schedule and competitiveness vary across regional groups (Africa has more seats and smoother rotation; WEOG has more contested elections).

While the regional rotation provides a degree of as-if randomness *within region-year cells*, the instrument is not strictly randomly assigned. Conditioning on region × year fixed effects and country fixed effects is essential.

## 6. Lag and anticipation channels

- **Anticipation (t-1, t-2):** Countries may receive more aid in the year(s) before their Council term as the U.S. seeks to influence upcoming votes. This creates pre-trend bias if not modeled.
- **Contemporaneous (t, t+1):** Aid effects may operate during the 2-year term.
- **Legacy (t+2, t+3):** Effects may persist after the term ends through continued aid relationships or changed diplomatic habits.

An event-study design with `unsc_{t-2}` through `unsc_{t+3}` indicators can disentangle these channels.

## 7. Preferred design

The preferred estimation strategy in order of strength of causal claim:

1. **Reduced form (most credible):** Regress pro-U.S. speech stance directly on UNSC membership with country and region-year fixed effects. This estimates whether UNSC membership changes how countries speak. It does not require the exclusion restriction.

2. **Event study:** Estimate the dynamic path around UNSC membership to test for pre-trends, contemporaneous effects, and post-term persistence.

3. **Matched sample:** Within each region-year, compare UNSC members to non-members with similar pre-treatment characteristics (prior aid levels, prior speech content, GDP, population).

4. **2SLS (requires the strongest assumptions):** Use UNSC membership to instrument for aid. Only proceed to 2SLS if:
   - First-stage F-statistic > 10 (Staiger-Stock rule of thumb)
   - Weak-IV robust confidence sets (Anderson-Rubin) do not reverse the conclusion
   - The exclusion restriction is discussed with specific threats, not dismissed with a footnote

## 8. Conditions that would force abandoning a causal claim

The paper should report null, negative, unstable, and sample-sensitive results. Specific conditions that would downgrade or abandon the causal interpretation:

1. **Pre-trends in speech stance before UNSC membership** (anticipation effects in event study).
2. **First-stage F-statistic < 10** or weak-IV robust confidence sets that include zero and economically large values of opposite sign.
3. **UNSC effect on speech content that is not mediated by aid** (e.g., the reduced form is significant but the 2SLS result is zero or wrong-signed — suggesting the exclusion restriction fails).
4. **Sample sensitivity:** Results that disappear when removing any single region or period.
5. **Zero or negligible magnitude:** Even if statistically significant, an effect size that is economically trivial (e.g., a 0.01 standard deviation change in stance).

In any of these cases, the paper should present the findings honestly as descriptive evidence or reduced-form correlations, without claiming that aid *causes* changes in allegiance.

## 9. Relationship to validation signal

`us_agree` (UN voting agreement) and `ideal_point` serve as external validation signals for the text-based outcome measure, not as training targets. They address the question: "Does my speech-based stance measure capture something real about a country's alignment with the U.S.?"

They must NOT be used:
- To select, tune, or train the speech measure
- As dependent variables in the main analysis (they are hard indicators, not text-based outcome)
- To choose between scoring rubrics after seeing aid effects

## 10. Estimand decision log

**Chosen estimand:** LATE of U.S. aid on pro-U.S. speech stance for UNSC compliers.

**Rejected alternatives:**
- ATE: Rejected because UNSC membership is not randomly assigned; compliance is heterogeneous.
- OLS/descriptive only: Rejected for the main analysis because the research question calls for testing whether aid changes behavior.
- Difference-in-differences (UNSC membership as treatment): Valid as reduced form; does not identify the aid channel.
