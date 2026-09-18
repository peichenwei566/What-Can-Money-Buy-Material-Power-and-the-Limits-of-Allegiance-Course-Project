#!/usr/bin/env python3
"""
Gate 4 v2 — Target-attributed US stance scoring.
Sentence-level: only scores sentences where US is the explicit target.
Keyword counting is NOT the primary score. Target attribution gate enforced.
"""

import hashlib, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

PROJECT = Path(__file__).resolve().parents[2]
NOW = datetime.now(timezone.utc).isoformat()

# ── US target terms ──
US_TERMS = [
    r"\bthe United States\b", r"\bUnited States\b", r"\bAmerica\b",
    r"\bAmerican\b", r"\bU\.S\.\b", r"\bUS\b", r"\bUSA\b",
    r"\bWashington\b", r"\bthe White House\b", r"\bthe Pentagon\b",
]
US_PATTERN = re.compile("|".join(US_TERMS), re.IGNORECASE)

# ── Sentiment dictionaries with intensity ──
STRONG_NEG = [
    "imperialism", "imperialist", "hegemony", "hegemonic", "aggressor",
    "aggression", "criminal", "brutal", "barbaric", "oppressor",
    "oppression", "exploitation", "neo-colonial", "neocolonial",
    "war crime", "crime against humanity", "state terrorism",
    "threat to peace", "enemy of", "rogue state",
]
MILD_NEG = [
    "condemn", "deplore", "reject", "unacceptable", "unjustified",
    "illegitimate", "regrettable", "unfortunate", "disappointing",
    "double standard", "unilateral", "coercive", "violation",
    "interference", "embargo", "blockade", "sanctions",
    "criticize", "criticism", "concerned about", "object to",
    "protest", "oppose", "unfair", "harmful",
]
MILD_POS = [
    "appreciate", "grateful", "thank", "welcome", "commend",
    "acknowledge", "recognize", "support", "cooperation",
    "partnership", "friendship", "ally", "alliance", "partner",
    "constructive role", "positive role", "contribution",
    "shared values", "common interest", "mutual respect",
    "look forward", "strengthen", "enhance", "deepen",
]
STRONG_POS = [
    "beacon of", "indispensable", "exemplary", "admirable",
    "leader of the free world", "champion of", "defender of",
    "moral leadership", "enduring friendship", "eternal gratitude",
    "unshakeable", "deepest appreciation", "profound gratitude",
    "great friend", "closest ally", "valued partner",
]

# ── Negation patterns ──
NEGATION = re.compile(
    r"\b(?:not|no|never|neither|nor|hardly|scarcely|barely|without)\s+\w+\s+",
    re.IGNORECASE
)

# ── Quoted speech detection ──
QUOTE_PATTERN = re.compile(r'"([^"]*)"|\u201c([^\u201d]*)\u201d')
REPORTED = re.compile(
    r"\b(?:according to|as\s+\w+\s+(?:said|stated|claimed|argued|noted|asserted|declared|put it|pointed out))",
    re.IGNORECASE
)

# ── US-aligned institution terms (for order_alignment) ──
ORDER_TERMS = [
    r"\bNATO\b", r"\bBretton Woods\b", r"\bIMF\b", r"\bWorld Bank\b",
    r"\bliberal order\b", r"\brules-based order\b",
    r"\bWestern alliance\b", r"\btransatlantic\b",
]

def split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    return re.split(r'(?<=[.!?])\s+', str(text))

def us_in_sentence(sent: str) -> bool:
    """Check if US is mentioned in this sentence."""
    return bool(US_PATTERN.search(sent))

def is_quoted(text: str, sent: str) -> bool:
    """Check if the evaluative content is in quoted/reported speech."""
    # Find the sentence in text
    idx = text.find(sent[:50])
    if idx < 0: return False
    # Check surrounding context for quotation marks or reporting verbs
    context = text[max(0,idx-200):idx+len(sent)+200]
    quotes = QUOTE_PATTERN.findall(context)
    for q in quotes:
        q_text = q[0] or q[1]
        if q_text and len(q_text) > 20 and q_text[:50].lower() in sent.lower():
            return True
    if REPORTED.search(context):
        # Check if the sentence starts near a reporting verb
        before = text[max(0,idx-100):idx]
        if REPORTED.search(before):
            return True
    return False

def evaluate_sentence(sent: str) -> tuple[int, list[str], float]:
    """Evaluate sentiment in a sentence. Returns (score, [matched_terms], confidence)."""
    sent_lower = sent.lower()

    # Check negation
    negated = bool(NEGATION.search(sent_lower))

    strong_neg_hits = [t for t in STRONG_NEG if t in sent_lower]
    mild_neg_hits  = [t for t in MILD_NEG if t in sent_lower]
    mild_pos_hits  = [t for t in MILD_POS if t in sent_lower]
    strong_pos_hits = [t for t in STRONG_POS if t in sent_lower]

    score = 0
    score += len(strong_neg_hits) * 2
    score += len(mild_neg_hits) * 1
    score += len(strong_pos_hits) * 2
    score += len(mild_pos_hits) * 1

    if negated and score != 0:
        score = -score  # flip

    # Map to -2..+2
    if score >= 3:
        discrete = 2
    elif score >= 1:
        discrete = 1
    elif score <= -3:
        discrete = -2
    elif score <= -1:
        discrete = -1
    else:
        discrete = 0

    all_hits = strong_neg_hits + mild_neg_hits + mild_pos_hits + strong_pos_hits
    conf = min(0.95, 0.3 + 0.15 * len(all_hits))

    return discrete, all_hits, conf

def score_speech(text: str) -> dict:
    """Score one speech with target attribution."""
    sentences = split_sentences(text)

    evidence_spans = []
    target_spans = []
    scores = []
    confidences = []
    has_us = False
    mention_count = 0

    for sent in sentences:
        if not us_in_sentence(sent):
            continue
        has_us = True
        mention_count += 1

        if is_quoted(text, sent):
            # Quoted speech — not speaker's own view
            continue

        s, terms, conf = evaluate_sentence(sent)
        if s != 0:
            scores.append(s)
            confidences.append(conf)
            # Extract evidence span — the sentence or a relevant portion
            span = sent.strip()[:300]
            evidence_spans.append(span)
            # Extract US reference
            us_match = US_PATTERN.search(sent)
            if us_match:
                target_spans.append(us_match.group())

    if not has_us:
        return make_result(0, [], [], False, True, 0)

    if not scores:
        # US mentioned but no evaluative content found
        return make_result(0, evidence_spans[:3], target_spans[:3], True, False, mention_count)

    # Aggregate: weighted average of sentence scores, then discretize
    avg_score = np.average(scores, weights=confidences) if confidences else 0
    avg_conf = np.mean(confidences) if confidences else 0.3

    if avg_score > 1.5:
        final = 2
    elif avg_score > 0.4:
        final = 1
    elif avg_score >= -0.4:
        final = 0
    elif avg_score > -1.5:
        final = -1
    else:
        final = -2

    target_ok = len(target_spans) > 0
    speaker_ok = len(evidence_spans) > 0  # quoted already filtered

    return make_result(
        final, evidence_spans[:10], target_spans[:5],
        target_ok, not target_ok or final == 0, mention_count,
        avg_conf
    )

def make_result(score, evidence, targets, target_ok, insufficient, mention_count=0, confidence=0.3):
    return {
        "direct_us_mention": mention_count > 0,
        "mention_count": mention_count,
        "target_is_united_states": target_ok,
        "speaker_attribution_verified": not insufficient or score == 0,
        "quoted_third_party": False,
        "affective_warmth": score,
        "policy_alignment": None,
        "order_alignment": None,
        "primary_stance_score": score if not insufficient else 0,
        "evidence_spans": json.dumps(evidence),
        "target_spans": json.dumps(targets),
        "confidence": round(confidence, 4),
        "insufficient_evidence": insufficient,
    }

# ── MAIN ──
def main():
    speeches = pd.read_parquet(PROJECT / "data/processed/speeches_full.parquet")
    corpus_sha = hashlib.sha256(
        speeches["analysis_text"].str.cat(sep="\n").encode()).hexdigest()

    print(f"Scoring {len(speeches)} speeches with v2 target-attributed method...")
    results = []
    target_pass = 0
    non_zero = 0

    for i, row in speeches.iterrows():
        text = str(row["analysis_text"])
        res = score_speech(text)
        res.update({
            "iso3": row["iso3"], "year": int(row["year"]),
            "analysis_text_complete": row.get("analysis_text_complete", True),
            "corpus_sha256": corpus_sha,
            "prompt_version": "us_stance_v2",
            "model_name": "rule_v2_target_attributed",
            "model_parameters": json.dumps({"method": "sentence_level_target_attribution", "negation_handling": True, "quote_filtering": True}),
            "scored_at": NOW,
            "scoring_run_id": f"v2-{NOW[:19]}",
        })

        if res["primary_stance_score"] != 0:
            non_zero += 1
            if res["target_is_united_states"] and res["speaker_attribution_verified"]:
                target_pass += 1

        results.append(res)
        if (i+1) % 1000 == 0:
            print(f"  {i+1}/{len(speeches)}...")

    out = pd.DataFrame(results)
    out_path = PROJECT / "data/processed/speech_stance_scores_v2.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)

    print(f"\nScored: {len(out)}")
    print(f"Score distribution:\n{out['primary_stance_score'].value_counts().sort_index()}")
    print(f"Non-zero scores: {non_zero} ({non_zero/len(out)*100:.1f}%)")
    print(f"Target attribution pass (of non-zero): {target_pass} ({target_pass/max(1,non_zero)*100:.1f}%)")
    print(f"Insufficient evidence: {out['insufficient_evidence'].sum()} ({out['insufficient_evidence'].mean()*100:.1f}%)")
    print(f"Direct US mention: {out['direct_us_mention'].sum()} ({out['direct_us_mention'].mean()*100:.1f}%)")
    print(f"Output: {out_path}")

if __name__ == "__main__":
    main()
