#!/usr/bin/env python3
"""Build blind stance annotations and run deterministic quality checks."""
from __future__ import annotations
import csv, hashlib, json, re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from review_contexts import paragraphs, direct_passage_count

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "inputs/blinded_stance_validation_200.csv"
RUBRIC = ROOT / "rubric/us_stance_v1.md"
OVERRIDES = ROOT / "code/validation/score_overrides.json"
OUTPUT = ROOT / "outputs/codex_stance_validation.csv"
QC_REPORT = ROOT / "outputs/validation_qc_report.md"
MANIFEST = ROOT / "outputs/validation_manifest.json"
SOURCE_INPUT = ROOT / "data/interim/blinded_stance_validation_200.csv"
SOURCE_RUBRIC = ROOT / "code/measurement/prompts/us_stance_v1.md"
STARTED_AT = "2026-07-29T20:29:20+08:00"
EXPECTED_INPUT_FIELDS = ["review_id", "iso3", "year", "analysis_text", "rubric_version"]
OUTPUT_FIELDS = ["review_id","iso3","year","direct_us_mention","mention_count","affective_warmth","policy_alignment","order_alignment","primary_stance_score","evidence_spans","confidence","insufficient_evidence","rationale_short","validator_type","rubric_version","annotated_at"]
FORBIDDEN_FIELDS = {"us_agree","ideal_point","aid","us_aid","unsc_seat","un_voting_alignment","treatment","outcome"}

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def count_mentions(text: str) -> int:
    return sum(direct_passage_count(p) for p in paragraphs(text))

def exact_span(text: str, proposed: str) -> str:
    if proposed in text: return proposed
    def normalized_with_map(value: str):
        chars=[]; mapping=[]; in_space=False
        for i,ch in enumerate(value):
            if ch.isspace():
                if not in_space: chars.append(" "); mapping.append(i)
                in_space=True
            else:
                chars.append(ch); mapping.append(i); in_space=False
        return "".join(chars),mapping
    norm_text,mapping=normalized_with_map(text)
    norm_span=re.sub(r"\s+"," ",proposed)
    pos=norm_text.find(norm_span)
    if pos<0: raise ValueError(f"Evidence not found: {proposed[:100]}")
    start=mapping[pos]; end=mapping[pos+len(norm_span)-1]+1
    return text[start:end]

def main() -> None:
    finished=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    with INPUT.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f); input_fields=reader.fieldnames or []; rows=list(reader)
    overrides=json.loads(OVERRIDES.read_text(encoding="utf-8"))
    annotations=[]
    for source in rows:
        count=count_mentions(source["analysis_text"])
        direct=count>0
        record={
            "review_id":source["review_id"],"iso3":source["iso3"],"year":int(source["year"]),
            "direct_us_mention":direct,"mention_count":count,"affective_warmth":0,
            "policy_alignment":0,"order_alignment":0,"primary_stance_score":0,
            "evidence_spans":[],"confidence":0.90 if direct else 0.97,
            "insufficient_evidence":True,
            "rationale_short":("Direct references are factual, quoted, historical, or otherwise non-evaluative; the text does not support a directional stance."
                               if direct else "No direct or contextually explicit reference to the United States provides evaluative evidence."),
            "validator_type":"codex_ai","rubric_version":source["rubric_version"],"annotated_at":finished,
        }
        override=overrides.get(source["review_id"],{})
        record.update(override)
        if not record["direct_us_mention"] and "rationale_short" not in override:
            record["confidence"]=0.97
            record["rationale_short"]="No direct or contextually explicit reference to the United States provides evaluative evidence."
        record["primary_stance_score"]=record["affective_warmth"]
        record["evidence_spans"]=[exact_span(source["analysis_text"],s) for s in record["evidence_spans"]]
        annotations.append(record)

    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with OUTPUT.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=OUTPUT_FIELDS,extrasaction="ignore",lineterminator="\n")
        writer.writeheader()
        for record in annotations:
            out=record.copy()
            out["direct_us_mention"]="true" if out["direct_us_mention"] else "false"
            out["insufficient_evidence"]="true" if out["insufficient_evidence"] else "false"
            out["evidence_spans"]=json.dumps(out["evidence_spans"],ensure_ascii=False)
            writer.writerow(out)

    input_ids=[r["review_id"] for r in rows]; output_ids=[r["review_id"] for r in annotations]
    scores=("affective_warmth","policy_alignment","order_alignment","primary_stance_score")
    checks={
        "input_output_count_match":len(rows)==len(annotations),
        "output_schema_exact":list(annotations[0].keys())==OUTPUT_FIELDS if annotations else False,
        "review_id_unique":len(output_ids)==len(set(output_ids)),
        "no_missing_or_duplicate_samples":set(input_ids)==set(output_ids) and len(input_ids)==len(output_ids),
        "scores_in_range":all(type(r[k]) is int and -2<=r[k]<=2 for r in annotations for k in scores),
        "primary_equals_affective":all(r["primary_stance_score"]==r["affective_warmth"] for r in annotations),
        "nonzero_scores_have_evidence":all(r["evidence_spans"] or not any(r[k] for k in scores) for r in annotations),
        "evidence_exactly_in_source":all(s in src["analysis_text"] for r,src in zip(annotations,rows) for s in r["evidence_spans"]),
        "insufficient_records_all_zero":all(not r["insufficient_evidence"] or all(r[k]==0 for k in scores) for r in annotations),
        "no_forbidden_input_fields":input_fields==EXPECTED_INPUT_FIELDS and not ({f.lower() for f in input_fields}&FORBIDDEN_FIELDS),
        "input_files_unchanged":sha256(INPUT)==sha256(SOURCE_INPUT) and sha256(RUBRIC)==sha256(SOURCE_RUBRIC),
        "rationales_within_80_words":all(len(r["rationale_short"].split())<=80 for r in annotations),
        "confidence_in_range":all(isinstance(r["confidence"],(int,float)) and 0<=r["confidence"]<=1 for r in annotations),
        "mention_fields_consistent":all(type(r["mention_count"]) is int and r["mention_count"]>=0 and r["direct_us_mention"]==(r["mention_count"]>0) for r in annotations),
        "fixed_metadata_valid":all(r["validator_type"]=="codex_ai" and r["rubric_version"]=="us_stance_v1" for r in annotations),
        "evidence_values_are_arrays":all(isinstance(r["evidence_spans"],list) and all(isinstance(s,str) for s in r["evidence_spans"]) for r in annotations),
    }
    passed=all(checks.values())
    score_dist={str(v):sum(r["primary_stance_score"]==v for r in annotations) for v in range(-2,3)}
    report=["# Codex Blind Stance Validation — QC Report","",f"- Completed: `{finished}`",f"- Input rows: **{len(rows)}**",f"- Output rows: **{len(annotations)}**",f"- Overall result: **{'PASS' if passed else 'FAIL'}**","","## Checks","","| Check | Result |","|---|---|"]
    report += [f"| `{name}` | {'PASS' if ok else 'FAIL'} |" for name,ok in checks.items()]
    report += ["","## Descriptive audit totals","",f"- Direct US mention: {sum(r['direct_us_mention'] for r in annotations)}",f"- Insufficient evidence: {sum(r['insufficient_evidence'] for r in annotations)}",f"- Primary score distribution: `{json.dumps(score_dist)}`","","No external country-relationship information or prohibited analytical variables were used. The previously supplied non-blind file was not read beyond its header and was not used in this run.",""]
    QC_REPORT.write_text("\n".join(report),encoding="utf-8")
    manifest={
        "input_file":"inputs/blinded_stance_validation_200.csv","input_sha256":sha256(INPUT),
        "rubric_file":"rubric/us_stance_v1.md","rubric_sha256":sha256(RUBRIC),
        "codex_model":"GPT-5 (Codex)","codex_run_mode":"Codex desktop; independent blind single-agent text review",
        "sample_count":len(rows),"started_at":STARTED_AT,"completed_at":finished,
        "output_file":"outputs/codex_stance_validation.csv","output_sha256":sha256(OUTPUT),
        "qc_report":"outputs/validation_qc_report.md","qc_report_sha256":sha256(QC_REPORT),
        "all_quality_checks_passed":passed,"quality_checks":checks,
        "input_fields":input_fields,"forbidden_variables_used":False,
    }
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if not passed: raise SystemExit("QC failed")
    print(json.dumps({"rows":len(annotations),"direct_mentions":sum(r["direct_us_mention"] for r in annotations),"insufficient":sum(r["insufficient_evidence"] for r in annotations),"score_distribution":score_dist,"checks":checks},indent=2))

if __name__=="__main__": main()
