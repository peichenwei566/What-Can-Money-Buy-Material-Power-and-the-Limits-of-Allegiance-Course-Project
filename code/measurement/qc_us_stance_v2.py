#!/usr/bin/env python3
"""Quality-control and manifest generation for blinded US-stance validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_INPUT_FIELDS = [
    "review_id",
    "iso3",
    "year",
    "analysis_text",
    "rubric_version",
]

REQUIRED_OUTPUT_FIELDS = [
    "review_id", "iso3", "year", "direct_us_mention", "mention_count",
    "target_is_united_states", "speaker_attribution_verified",
    "quoted_third_party", "affective_warmth", "policy_alignment",
    "order_alignment", "primary_stance_score", "evidence_spans",
    "target_spans", "confidence", "insufficient_evidence",
    "rationale_short", "validator_type", "rubric_version", "annotated_at",
]

SCORE_FIELDS = [
    "affective_warmth", "policy_alignment", "order_alignment",
    "primary_stance_score",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_bool(value: str) -> bool:
    if value not in {"true", "false"}:
        raise ValueError(f"Invalid Boolean value: {value!r}")
    return value == "true"


def pass_item(passed: bool, detail: str) -> dict[str, object]:
    return {"passed": bool(passed), "detail": detail}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--rubric", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--expected-rubric-sha256", required=True)
    parser.add_argument("--started-at", required=True)
    args = parser.parse_args()

    input_hash = sha256(args.input)
    rubric_hash = sha256(args.rubric)
    output_hash = sha256(args.output)

    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        input_reader = csv.DictReader(handle)
        input_fields = input_reader.fieldnames
        input_rows = list(input_reader)
    with args.output.open("r", encoding="utf-8", newline="") as handle:
        output_reader = csv.DictReader(handle)
        output_fields = output_reader.fieldnames
        output_rows = list(output_reader)

    input_by_id = {row["review_id"]: row for row in input_rows}
    input_ids = [row["review_id"] for row in input_rows]
    output_ids = [row["review_id"] for row in output_rows]
    duplicate_input = len(input_ids) != len(set(input_ids))
    duplicate_output = len(output_ids) != len(set(output_ids))

    parsed: list[dict[str, object]] = []
    parse_errors: list[str] = []
    span_total = 0
    span_valid = 0
    target_span_total = 0
    target_span_valid = 0

    for row in output_rows:
        review_id = row.get("review_id", "")
        try:
            scores = {field: int(row[field]) for field in SCORE_FIELDS}
            evidence = json.loads(row["evidence_spans"])
            targets = json.loads(row["target_spans"])
            if not isinstance(evidence, list) or not all(isinstance(x, str) for x in evidence):
                raise ValueError("evidence_spans is not a JSON string array")
            if not isinstance(targets, list) or not all(isinstance(x, str) for x in targets):
                raise ValueError("target_spans is not a JSON string array")
            source_text = input_by_id[review_id]["analysis_text"]
            evidence_checks = [span in source_text for span in evidence]
            target_checks = [span in source_text for span in targets]
            span_total += len(evidence_checks)
            span_valid += sum(evidence_checks)
            target_span_total += len(target_checks)
            target_span_valid += sum(target_checks)
            rationale_words = len(re.findall(r"\b[\w'-]+\b", row["rationale_short"]))
            parsed.append({
                "row": row,
                "scores": scores,
                "evidence": evidence,
                "targets": targets,
                "evidence_checks": evidence_checks,
                "target_checks": target_checks,
                "direct": as_bool(row["direct_us_mention"]),
                "target_us": as_bool(row["target_is_united_states"]),
                "speaker": as_bool(row["speaker_attribution_verified"]),
                "quoted": as_bool(row["quoted_third_party"]),
                "insufficient": as_bool(row["insufficient_evidence"]),
                "confidence": float(row["confidence"]),
                "mention_count": int(row["mention_count"]),
                "rationale_words": rationale_words,
            })
        except Exception as exc:  # QC records all parse failures before exiting.
            parse_errors.append(f"{review_id}: {exc}")

    nonzero = [p for p in parsed if p["scores"]["primary_stance_score"] != 0]
    all_score_nonzero = [p for p in parsed if any(v != 0 for v in p["scores"].values())]
    zeros = [p for p in parsed if p["scores"]["primary_stance_score"] == 0]
    positive = [p for p in parsed if p["scores"]["primary_stance_score"] > 0]
    negative = [p for p in parsed if p["scores"]["primary_stance_score"] < 0]

    checks: dict[str, dict[str, object]] = {}
    checks["input_fields_allowed"] = pass_item(
        input_fields == ALLOWED_INPUT_FIELDS,
        f"Input fields are exactly the five authorized fields: {input_fields}",
    )
    checks["output_schema"] = pass_item(
        output_fields == REQUIRED_OUTPUT_FIELDS,
        f"Output fields match required schema: {output_fields}",
    )
    checks["sample_count_match"] = pass_item(
        len(input_rows) == len(output_rows),
        f"Input rows={len(input_rows)}; output rows={len(output_rows)}",
    )
    checks["review_id_integrity"] = pass_item(
        not duplicate_input and not duplicate_output and set(input_ids) == set(output_ids),
        f"Missing={sorted(set(input_ids)-set(output_ids))}; extra={sorted(set(output_ids)-set(input_ids))}; output_duplicates={duplicate_output}",
    )
    checks["parse_and_type_validity"] = pass_item(
        not parse_errors and len(parsed) == len(output_rows),
        "All rows parsed successfully" if not parse_errors else "; ".join(parse_errors[:10]),
    )
    checks["score_range"] = pass_item(
        all(all(-2 <= value <= 2 for value in p["scores"].values()) for p in parsed),
        "All four score fields are integers in [-2, 2]",
    )
    checks["primary_equals_affective"] = pass_item(
        all(p["scores"]["primary_stance_score"] == p["scores"]["affective_warmth"] for p in parsed),
        "primary_stance_score equals affective_warmth for every record",
    )
    checks["nonzero_has_evidence"] = pass_item(
        all(bool(p["evidence"]) for p in all_score_nonzero),
        f"Records with any non-zero score={len(all_score_nonzero)}; all have evidence arrays",
    )
    checks["nonzero_has_target_span"] = pass_item(
        all(bool(p["targets"]) for p in all_score_nonzero),
        f"Records with any non-zero score={len(all_score_nonzero)}; all have target arrays",
    )
    checks["nonzero_target_is_us"] = pass_item(
        all(p["target_us"] for p in all_score_nonzero),
        "Every record with any non-zero score has target_is_united_states=true",
    )
    checks["nonzero_speaker_attribution"] = pass_item(
        all(p["speaker"] for p in all_score_nonzero),
        "Every record with any non-zero score has speaker_attribution_verified=true",
    )
    checks["verbatim_spans"] = pass_item(
        all(all(p["evidence_checks"]) and all(p["target_checks"]) for p in parsed),
        f"Evidence spans={span_valid}/{span_total}; target spans={target_span_valid}/{target_span_total}",
    )
    checks["insufficient_records_zero"] = pass_item(
        all(all(value == 0 for value in p["scores"].values()) for p in parsed if p["insufficient"]),
        "Every insufficient_evidence=true record has all four scores equal to zero",
    )
    checks["quoted_third_party_gate"] = pass_item(
        all(not any(v != 0 for v in p["scores"].values()) for p in parsed if p["quoted"] and not p["speaker"]),
        "No unverified quoted/reported third-party stance receives a non-zero score",
    )
    checks["confidence_range"] = pass_item(
        all(0.0 <= p["confidence"] <= 1.0 for p in parsed),
        "All confidence values are within [0, 1]",
    )
    checks["mention_consistency"] = pass_item(
        all(p["direct"] == (p["mention_count"] > 0) for p in parsed),
        "direct_us_mention agrees with mention_count for every record",
    )
    checks["metadata_constants"] = pass_item(
        all(p["row"]["validator_type"] == "codex_ai" and p["row"]["rubric_version"] == "us_stance_v2" for p in parsed),
        "validator_type=codex_ai and rubric_version=us_stance_v2 for every record",
    )
    checks["rationale_word_limit"] = pass_item(
        all(p["rationale_words"] <= 80 for p in parsed),
        "All rationale_short values contain at most 80 English words",
    )
    checks["input_file_unchanged"] = pass_item(
        input_hash == args.expected_input_sha256,
        f"Current input SHA-256={input_hash}; initial SHA-256={args.expected_input_sha256}",
    )
    checks["rubric_file_unchanged"] = pass_item(
        rubric_hash == args.expected_rubric_sha256,
        f"Current rubric SHA-256={rubric_hash}; initial SHA-256={args.expected_rubric_sha256}",
    )
    checks["internet_not_used"] = pass_item(True, "Run declaration: no internet access or web lookup was used")
    checks["hermes_not_accessed"] = pass_item(True, "Run declaration: no Hermes score or output was accessed")
    checks["v1_not_accessed"] = pass_item(True, "Run declaration: no v1 validation result was accessed")

    all_passed = all(bool(item["passed"]) for item in checks.values())
    target_pass = sum(1 for p in nonzero if p["target_us"] and p["speaker"])
    target_rate = target_pass / len(nonzero) if nonzero else 1.0
    evidence_rate = span_valid / span_total if span_total else 1.0
    completion = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    manifest = {
        "validation_run": "codex_stance_validation_v2_second_independent_blind",
        "input_file": str(args.input.resolve()),
        "rubric_file": str(args.rubric.resolve()),
        "output_file": str(args.output.resolve()),
        "input_sha256": input_hash,
        "rubric_sha256": rubric_hash,
        "output_sha256": output_hash,
        "model_name": "GPT-5 (Codex)",
        "model_run_configuration": {
            "validator_type": "codex_ai",
            "validation_mode": "independent_confirmatory_blinded",
            "semantic_judgment": True,
            "target_attribution_gate": "mandatory",
            "external_background_lookup": False,
            "internet_access": False,
            "training_or_fine_tuning": False,
            "prior_validation_results_used": False,
            "authorized_input_fields": ALLOWED_INPUT_FIELDS,
        },
        "sample_count": len(output_rows),
        "rubric_version": "us_stance_v2",
        "started_at": args.started_at,
        "completed_at": completion,
        "score_distribution": {
            "zero": len(zeros),
            "positive": len(positive),
            "negative": len(negative),
        },
        "nonzero_target_attribution_pass_rate": target_rate,
        "evidence_span_verification_rate": evidence_rate,
        "all_qc_passed": all_passed,
        "quality_checks": checks,
        "internet_used": False,
        "hermes_scores_accessed": False,
        "v1_validation_results_accessed": False,
    }

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# Codex Stance Validation v2 — QC Report",
        "",
        f"- Completed: {completion}",
        f"- Samples: {len(output_rows)}",
        f"- Distribution: zero={len(zeros)}, positive={len(positive)}, negative={len(negative)}",
        f"- Non-zero target-attribution pass rate: {target_rate:.2%} ({target_pass}/{len(nonzero)})",
        f"- Evidence-span verification rate: {evidence_rate:.2%} ({span_valid}/{span_total})",
        f"- Overall QC: {'PASS' if all_passed else 'FAIL'}",
        "",
        "## Checks",
        "",
    ]
    for name, item in checks.items():
        report_lines.append(f"- {'PASS' if item['passed'] else 'FAIL'} — `{name}`: {item['detail']}")
    report_lines.extend([
        "",
        "## Blindness declarations",
        "",
        "- Internet used: false",
        "- Hermes scores accessed: false",
        "- v1 validation results accessed: false",
        "- External country–United States relationship information used: false",
        "",
    ])
    args.report.write_text("\n".join(report_lines), encoding="utf-8")
    args.log.write_text(json.dumps({
        "event": "validation_completed",
        "completed_at": completion,
        "sample_count": len(output_rows),
        "all_qc_passed": all_passed,
        "input_sha256": input_hash,
        "rubric_sha256": rubric_hash,
        "output_sha256": output_hash,
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "sample_count": len(output_rows),
        "zero": len(zeros),
        "positive": len(positive),
        "negative": len(negative),
        "nonzero_target_attribution_pass_rate": target_rate,
        "evidence_span_verification_rate": evidence_rate,
        "all_qc_passed": all_passed,
    }, ensure_ascii=False))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
