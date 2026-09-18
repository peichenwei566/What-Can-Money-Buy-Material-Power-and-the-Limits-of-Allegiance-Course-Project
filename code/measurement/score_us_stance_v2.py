#!/usr/bin/env python3
"""Generate the second independent blinded US-stance validation CSV.

This script reads only the five fields authorized by the frozen protocol. The
semantic decisions below were made independently from analysis_text and are
encoded as review-level annotations. Evidence is extracted verbatim from the
source text at run time, so a changed corpus or a mismatched anchor fails fast.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ALLOWED_INPUT_FIELDS = [
    "review_id",
    "iso3",
    "year",
    "analysis_text",
    "rubric_version",
]

OUTPUT_FIELDS = [
    "review_id",
    "iso3",
    "year",
    "direct_us_mention",
    "mention_count",
    "target_is_united_states",
    "speaker_attribution_verified",
    "quoted_third_party",
    "affective_warmth",
    "policy_alignment",
    "order_alignment",
    "primary_stance_score",
    "evidence_spans",
    "target_spans",
    "confidence",
    "insufficient_evidence",
    "rationale_short",
    "validator_type",
    "rubric_version",
    "annotated_at",
]


def ann(
    score: int,
    policy: int,
    order: int,
    phrase: str,
    target: str,
    rationale: str,
    confidence: float,
    *,
    previous: int = 0,
    following: int = 0,
) -> dict[str, object]:
    return {
        "score": score,
        "policy": policy,
        "order": order,
        "phrase": phrase,
        "target": target,
        "rationale": rationale,
        "confidence": confidence,
        "previous": previous,
        "following": following,
    }


# Confirmatory annotations. A non-zero primary score appears only when the
# target-attribution gate is satisfied in the speaker government's own voice.
ANNOTATIONS = {
    "V2-0006": ann(1, 1, 0, "initiative of the United States Government for a rapprochement with the People's Republic of China are facts which show that goodwill", "United States Government", "The government positively evaluates the U.S. rapprochement initiative as evidence that goodwill and perseverance can advance peace.", 0.90),
    "V2-0007": ann(1, 1, 0, "We also welcome the decision by the United States to withdraw its forces from the area", "United States", "The speaker explicitly welcomes a United States withdrawal decision and links it to easing the regional situation.", 0.96),
    "V2-0011": ann(1, 1, 0, "My Government, in this connexion, supports the efforts of the Government of the United States", "Government of the United States", "The speaker's government explicitly supports United States efforts toward a just and lasting peace.", 0.97),
    "V2-0016": ann(-1, -1, 0, "the visit of Ian Smith to the United States not only compromises the position of the United States as a broker", "United States", "The government says the permitted visit compromises the United States as a broker and jeopardizes renewed negotiations.", 0.94),
    "V2-0018": ann(-1, -1, -1, "The major developed countries, led by the United States, have blocked all progress", "United States", "The speaker directly faults the United States for leading developed countries in blocking progress on global negotiations.", 0.97),
    "V2-0019": ann(-2, -2, -2, "the Government of the United States of America unscrupulously resorted to the use of the veto", "United States of America", "The government harshly accuses the United States of an unscrupulous veto and ties it to apartheid and denial of human rights.", 0.99, following=1),
    "V2-0021": ann(-1, -1, 0, "the United States Government has thought fit to extend the conflict to Laos and Cambodia", "United States Government", "The speaker criticizes the United States for extending the conflict and calls for it to leave the affected peoples alone.", 0.96, following=2),
    "V2-0025": ann(1, 1, 0, "The step recently taken by the President of the United States of America", "United States of America", "The jointly taken disarmament step involving the United States President is called heartening and a source of hope.", 0.91),
    "V2-0032": ann(1, 1, 0, "congratulates the Governments of the Republic of Panama and the United States of America upon the successful outcome", "United States of America", "A quoted statement issued by the speaker's own government congratulates the United States and Panama on successful negotiations.", 0.98),
    "V2-0033": ann(1, 1, 0, "A historic example of how goodwill and genuine foresight can eliminate situations", "United States of America", "The government presents the United States-Panama settlement as a historic model of goodwill and genuine foresight.", 0.94),
    "V2-0037": ann(1, 1, 0, "the recent historic understanding between the United States and the Soviet Union", "United States", "The speaker calls the United States-Soviet disarmament understanding historic and the basis for major hope.", 0.95),
    "V2-0043": ann(1, 1, 0, "As the result of certain initiatives taken by the United States recently, positive developments have taken place", "United States", "The speaker credits recent United States initiatives with positive developments and genuine opportunities for settlement.", 0.96),
    "V2-0049": ann(1, 1, 0, "My delegation identifies with the positive elements of the United States proposal", "United States", "The delegation explicitly identifies with positive elements of a United States proposal.", 0.97),
    "V2-0051": ann(1, 1, 0, "we welcome the signing of the second SALT Treaty between the United States and the USSR", "United States", "The government explicitly welcomes the United States-Soviet treaty and hopes it will produce further disarmament.", 0.97),
    "V2-0055": ann(-2, -2, -2, "a racist regime with the support of the forces of imperialism led by the United States of America", "United States of America", "The speaker depicts the United States as leading imperialist forces that support a racist regime.", 0.99),
    "V2-0056": ann(-1, -1, -1, "due to the support of the United States to Israel and its recurrent use of the veto", "United States", "The speaker faults United States support and repeated vetoes for preventing action against practices described as inhuman.", 0.97),
    "V2-0059": ann(1, 1, 0, "express my appreciation for the active efforts being jointly made by the Secretary of State, Mr. Kissinger, of the United States", "United States", "The speaker explicitly expresses appreciation for active efforts by the United States Secretary of State.", 0.98, following=1),
    "V2-0060": ann(1, 1, 0, "congratulate the Governments of Panama and the United States", "United States", "The delegation directly congratulates the United States and Panama for signing the canal treaties.", 0.98),
    "V2-0061": ann(1, 1, 0, "Kuwait welcomes the tentative agreement reached between the United States of America and the Soviet Union", "United States of America", "Kuwait explicitly welcomes the United States-Soviet missile agreement as a possible beginning of sustained disarmament.", 0.96),
    "V2-0064": ann(2, 2, 0, "recognize that the United States of America has on many occasions taken concrete measures for military disengagement", "United States of America", "The government strongly defends United States conduct, praising repeated concrete measures and proposals while rejecting accusations against it.", 0.96, following=1),
    "V2-0066": ann(1, 1, 0, "summit meeting between President Ronald Reagan of the United States and Mikhail S. Gorbachev", "United States", "The speaker says the summit involving the United States President kindled new hopes for accelerated détente.", 0.90),
    "V2-0067": ann(1, 1, 0, "The improved bilateral relations between the United States and the Soviet Union", "United States", "The speaker positively evaluates improved United States-Soviet relations and their effects on arms-reduction efforts.", 0.94),
    "V2-0070": ann(1, 1, 0, "The United States draft of a chemical weapons treaty represents an important contribution", "United States", "The government explicitly calls the United States treaty draft an important contribution to negotiations.", 0.98),
    "V2-0072": ann(-2, -2, -2, "This is a truly ominous decision, taken in the interests of the military-industrial complex of the United States", "United States", "The speaker calls the United States nuclear modernization decision truly ominous and attributes it to its military-industrial complex.", 0.99),
    "V2-0075": ann(1, 1, 0, "Some examples of the changes taking place in the world are the move in Soviet-United States relations from confrontation to dialogue", "United States", "The speaker presents the shift in United States-Soviet relations from confrontation to dialogue as a positive global change.", 0.89),
    "V2-0076": ann(1, 1, 0, "worth emphasizing the importance for the consolidation of peace of the well-known agreements between the USSR and the United States of America", "United States of America", "The speaker emphasizes the importance of United States-Soviet agreements for consolidating peace.", 0.94),
    "V2-0078": ann(2, 0, 2, "Italy's friendship with the United States", "United States", "The government explicitly affirms friendship with the United States and says that strategic choice remains valid and accords with United Nations ideals.", 0.98, following=1),
    "V2-0080": ann(-2, -2, -2, "The aggressive war against the peoples of Indo-China continues", "Government of the United States", "The speaker frames the conflict as an aggressive war and directly accuses the United States Government of refusing a constructive peace approach.", 0.98, following=1),
    "V2-0088": ann(1, 1, 0, "the Bahamas especially applauds the determined efforts of those countries", "United States of America", "The Bahamas explicitly applauds determined economic-balancing efforts by a group that expressly includes the United States.", 0.91),
    "V2-0089": ann(1, 1, 0, "co-operating very closely and successfully with the United States of America", "United States of America", "The government describes its bilateral cooperation with the United States as very close and successful.", 0.97),
    "V2-0090": ann(1, 1, 0, "The United States and the Syrian Arab Republic have played a very sensitive role in this peace process", "United States", "In a passage giving credit for peace efforts, the speaker positively characterizes the United States role in the process.", 0.88),
    "V2-0091": ann(2, 0, 2, "our former Trustee, now our good friend in a relationship of equality", "United States of America", "The speaker explicitly praises the former trustee as indispensable to national progress and now a good friend, then identifies it as the United States.", 0.99, following=1),
    "V2-0095": ann(1, 1, 0, "We are pleased that both the United States and the USSR now intend to pay their past dues", "United States", "The government explicitly expresses pleasure at the United States intention to meet its United Nations financial obligations.", 0.97),
    "V2-0102": ann(1, 1, 0, "We welcome the recent efforts of the United States of America", "United States of America", "The speaker explicitly welcomes United States efforts toward denuclearization and reduced tensions.", 0.98),
    "V2-0106": ann(1, 1, 0, "congratulate the Governments of the United States of America and the Republic of Cuba", "United States of America", "The government directly congratulates the United States and Cuba on restoring diplomatic relations.", 0.98),
    "V2-0109": ann(1, 0, 0, "deep sympathy and compassion of the Government and people of the Comoros to the American people and Government", "American people and Government", "The speaker conveys the government's deep sympathy and compassion directly to the American people and Government.", 0.99),
    "V2-0110": ann(1, 1, 0, "wishes to thank the United States Government for its contribution", "United States Government", "The government explicitly thanks the United States Government for a contribution supporting the peace process.", 0.99),
    "V2-0121": ann(1, 0, 0, "express its sympathy to the American people", "American people", "The delegation explicitly expresses sympathy to the American people after the terrorist attacks.", 0.98),
    "V2-0132": ann(1, 1, 0, "we welcome the return of the United States to the United Nations Educational, Scientific and Cultural Organization", "United States", "The government explicitly welcomes the United States return to UNESCO.", 0.99),
    "V2-0133": ann(1, 0, 0, "our sincere feeling of solidarity with the women and men of the United States", "United States", "The speaker expresses sincere solidarity with people of the United States suffering after natural disasters.", 0.99),
    "V2-0136": ann(-1, -1, -1, "the United States has been considered the country that issues the money used as reserve currency par excellence, it ends up being outside of the whole system", "United States", "The speaker criticizes the United States for benefiting from reserve-currency status and escaping scrutiny applied to other countries.", 0.92, following=1),
    "V2-0137": ann(1, 1, 0, "our great satisfaction at the political agreements reached by Canada, the United States and Mexico", "United States", "The government expresses great satisfaction with political trade agreements expressly including the United States.", 0.96),
    "V2-0140": ann(1, 1, 0, "Our deep gratitude goes also to the six countries that constitute the Group of Friends", "United States of America", "The speaker extends deep gratitude to a six-country peace group explicitly including the United States.", 0.97, following=1),
    "V2-0142": ann(-1, -1, 0, "the United States, the United Kingdom and China have no reason not to join them", "United States", "The speaker mildly rebukes the United States for not joining the nuclear-testing moratorium.", 0.96),
    "V2-0152": ann(-1, -1, 0, "We expect to be able to be part of a just and comprehensive solution and that the action of the United States will match its rhetoric", "United States", "The government voices clear skepticism that United States action will match its rhetoric on an even-handed peace role.", 0.94),
    "V2-0159": ann(2, 2, 2, "at the forefront of which stand the people of the United States of American and Great Britain", "United States of American", "The speaker gives emphatic gratitude to the United States-led coalition and says Iraqis will never forget its courage and sacrifice.", 0.99, following=1),
    "V2-0162": ann(-2, -2, -2, "an illegitimate international coalition led by the United States under the pretext of combating terrorism in Syria", "United States", "The government calls the United States-led coalition illegitimate and accuses it of aligning with terrorists and causing chaos, killing and destruction.", 0.99, following=2),
    "V2-0164": ann(-2, -2, -2, "mobilized, under United States leadership, all the forces of evil against Iraq", "United States", "The speaker describes United States leadership as mobilizing all forces of evil to attack and destroy Iraq.", 0.99),
    "V2-0166": ann(1, 1, 0, "The United States has announced its decision to extend the moratorium", "United States", "The government positively evaluates the United States moratorium as conducive to negotiating a comprehensive test ban.", 0.94, following=1),
    "V2-0170": ann(1, 1, 0, "We agree with the United States that this matter should urgently be dealt with by the Security Council", "United States", "The speaker explicitly agrees with the United States position on urgent Security Council consideration.", 0.97),
    "V2-0176": ann(1, 1, 0, "We welcome the agreement on economic normalization between Kosova and Serbia, brokered and guaranteed by the President of the United States", "United States", "The government welcomes an agreement brokered and guaranteed by the United States President.", 0.96),
    "V2-0177": ann(1, 1, 0, "The positive trend in disarmament and non-proliferation has been strengthened by", "United States", "The speaker says United States-Russian commitments strengthened the positive disarmament and non-proliferation trend.", 0.94),
    "V2-0182": ann(1, 1, 1, "We support no less the United States initiative to promote an effective and meaningful reform of the United Nations", "United States", "The government explicitly supports a United States initiative for effective and meaningful United Nations reform.", 0.99),
    "V2-0183": ann(2, 0, 2, "I will never forget our gratitude to the Allies and our host country", "United States", "After identifying the host country as the United States, the speaker expresses enduring gratitude for liberation, peace and freedom.", 0.98, previous=2),
}


# These records contain lexical candidates such as Latin America, inter-
# American, or Washington as a venue, but no semantic reference to the U.S.
FORCE_NO_US = {
    "V2-0003", "V2-0005", "V2-0017", "V2-0026", "V2-0028",
    "V2-0030", "V2-0031", "V2-0035", "V2-0036", "V2-0038",
    "V2-0045", "V2-0048", "V2-0057", "V2-0058", "V2-0073",
    "V2-0074", "V2-0077", "V2-0086", "V2-0087", "V2-0093",
    "V2-0119", "V2-0125", "V2-0126", "V2-0130", "V2-0131",
    "V2-0138", "V2-0141", "V2-0146", "V2-0161", "V2-0178",
    "V2-0186", "V2-0190", "V2-0196",
}

MIXED_ZERO = {
    "V2-0034": "The speech criticizes a United States economic measure but also explicitly admires the country's international role, producing a mixed affective assessment.",
    "V2-0117": "The speech calls United States sanctions unjust while also describing the United States as a great country, producing a mixed affective assessment.",
}

THIRD_PARTY_ZERO = {"V2-0024", "V2-0194"}


def flexible_pattern(phrase: str) -> re.Pattern[str]:
    parts = re.findall(r"\S+", phrase)
    return re.compile(r"\s+".join(re.escape(part) for part in parts))


def sentence_boundaries(text: str) -> list[tuple[int, int]]:
    boundaries = [0]
    for match in re.finditer(r"[.!?](?:[\"'”’])?(?=\s|$)", text):
        boundaries.append(match.end())
    if boundaries[-1] != len(text):
        boundaries.append(len(text))
    spans = []
    for left, right in zip(boundaries, boundaries[1:]):
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
        if left < right:
            spans.append((left, right))
    return spans


def extract_evidence(text: str, item: dict[str, object]) -> str:
    matches = list(flexible_pattern(str(item["phrase"])).finditer(text))
    if len(matches) != 1:
        raise ValueError(f"Evidence anchor matched {len(matches)} times: {item['phrase']!r}")
    match = matches[0]
    spans = sentence_boundaries(text)
    containing = [i for i, (left, right) in enumerate(spans) if left <= match.start() < right]
    if len(containing) != 1:
        raise ValueError(f"Could not isolate sentence for anchor: {item['phrase']!r}")
    index = containing[0]
    first = max(0, index - int(item["previous"]))
    last = min(len(spans) - 1, index + int(item["following"]))
    evidence = text[spans[first][0] : spans[last][1]]
    if evidence not in text:
        raise AssertionError("Extracted evidence is not verbatim")
    return evidence


def extract_target(evidence: str, target_phrase: str) -> str:
    match = flexible_pattern(target_phrase).search(evidence)
    if not match:
        raise ValueError(f"Target {target_phrase!r} is not inside evidence")
    return match.group(0)


def semantic_mentions(review_id: str, text: str) -> list[str]:
    if review_id in FORCE_NO_US:
        return []

    candidates: list[tuple[int, int, str]] = []
    patterns = [
        re.compile(r"(?<![A-Za-z])[Uu]nited\s+[Ss]tates(?:\s+of\s+[Aa]merica)?(?![A-Za-z])"),
        re.compile(r"(?<![A-Za-z])U\.?\s*S\.?(?:\s*A\.?)?(?![A-Za-z])"),
        re.compile(r"(?<![A-Za-z])(?:America|American|Americans)(?![A-Za-z])", re.IGNORECASE),
        re.compile(r"(?<![A-Za-z])Washington(?![A-Za-z])"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            before = text[max(0, match.start() - 40) : match.start()]
            after = text[match.end() : min(len(text), match.end() + 40)]
            token = match.group(0)
            if re.fullmatch(r"U\.?\s*S\.?(?:\s*A\.?)?", token):
                if before.rstrip().endswith("$") or re.match(r"\s*(?:\$|\d|dollars?\b)", after, re.IGNORECASE):
                    continue
            if token.lower().startswith("america"):
                if re.search(r"(?:Latin|Central|South|North|inter)[ -]?$", before, re.IGNORECASE):
                    continue
                if re.match(r"\s+(?:States|continent|countries|region|family|initiative)\b", after, re.IGNORECASE):
                    continue
                if re.search(r"Organization of\s*$", before, re.IGNORECASE):
                    continue
            if token == "Washington":
                if re.search(r"(?:in|at|held in|signed in)\s*$", before, re.IGNORECASE):
                    continue
                if re.match(r"\s+(?:D\.?C\.?|summit|agreement|agreements|declaration|consensus)\b", after, re.IGNORECASE):
                    continue
            candidates.append((match.start(), match.end(), token))

    candidates.sort()
    mentions: list[str] = []
    last_end = -1
    for start, end, token in candidates:
        if start >= last_end:
            mentions.append(token)
            last_end = end
    return mentions


def write_output(input_path: Path, output_path: Path, annotated_at: str) -> None:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ALLOWED_INPUT_FIELDS:
            raise SystemExit(
                "Blind-field check failed. Expected exactly "
                f"{ALLOWED_INPUT_FIELDS}, found {reader.fieldnames}."
            )
        rows = list(reader)

    review_ids = [row["review_id"] for row in rows]
    unknown = sorted(set(ANNOTATIONS) - set(review_ids))
    if unknown:
        raise SystemExit(f"Annotations contain unknown review_id values: {unknown}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for source in rows:
            review_id = source["review_id"]
            text = source["analysis_text"]
            mentions = semantic_mentions(review_id, text)
            item = ANNOTATIONS.get(review_id)
            quoted = review_id in THIRD_PARTY_ZERO

            if item:
                try:
                    evidence = extract_evidence(text, item)
                    target = extract_target(evidence, str(item["target"]))
                except ValueError as exc:
                    raise ValueError(f"{review_id}: {exc}") from exc
                score = int(item["score"])
                policy = int(item["policy"])
                order = int(item["order"])
                confidence = float(item["confidence"])
                rationale = str(item["rationale"])
                evidence_spans = [evidence]
                target_spans = [target]
                target_verified = True
                attribution_verified = True
                insufficient = False
                if not mentions:
                    raise ValueError(f"Non-zero annotation lacks a computed U.S. mention: {review_id}")
            else:
                score = policy = order = 0
                confidence = 0.96 if not mentions else 0.88
                evidence_spans = []
                target_spans = []
                target_verified = bool(mentions)
                attribution_verified = bool(mentions) and not quoted
                insufficient = review_id not in MIXED_ZERO
                if review_id in MIXED_ZERO:
                    rationale = MIXED_ZERO[review_id]
                    confidence = 0.86
                elif review_id == "V2-0194":
                    rationale = "The speech narrates historical U.S. nuclear testing and reports responsibility, but lacks a sufficiently explicit own-voice evaluation targeting the United States under the frozen gate."
                    confidence = 0.78
                elif mentions:
                    rationale = "The United States is mentioned, but only factually, geographically, ceremonially, or without a clear evaluative statement by the speaker's government."
                else:
                    rationale = "No explicit United States target appears in the speech; the frozen target-attribution gate is not met."

            if len(re.findall(r"\b[\w'-]+\b", rationale)) > 80:
                raise ValueError(f"Rationale exceeds 80 English words: {review_id}")

            out = {
                "review_id": review_id,
                "iso3": source["iso3"],
                "year": source["year"],
                "direct_us_mention": str(bool(mentions)).lower(),
                "mention_count": len(mentions),
                "target_is_united_states": str(target_verified).lower(),
                "speaker_attribution_verified": str(attribution_verified).lower(),
                "quoted_third_party": str(quoted).lower(),
                "affective_warmth": score,
                "policy_alignment": policy,
                "order_alignment": order,
                "primary_stance_score": score,
                "evidence_spans": json.dumps(evidence_spans, ensure_ascii=False),
                "target_spans": json.dumps(target_spans, ensure_ascii=False),
                "confidence": f"{confidence:.2f}",
                "insufficient_evidence": str(insufficient).lower(),
                "rationale_short": rationale,
                "validator_type": "codex_ai",
                "rubric_version": source["rubric_version"],
                "annotated_at": annotated_at,
            }
            writer.writerow(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--annotated-at", required=True)
    args = parser.parse_args()
    write_output(args.input, args.output, args.annotated_at)


if __name__ == "__main__":
    main()
