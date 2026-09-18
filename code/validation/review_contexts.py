#!/usr/bin/env python3
"""Print blind-review context around possible references to the United States."""
from __future__ import annotations
import argparse, csv, json, re
from pathlib import Path

DIRECT_RE = re.compile(
    r"\bUnited States(?: of America)?\b|\bU\.S\.(?:A\.)?\b|\bUSA\b|\bWashington\b|"
    r"\b(?:President\s+)?(?:Ronald\s+)?Reagan\b|\b(?:President\s+)?(?:George\s+(?:H\.\s*W\.\s*|W\.\s*)?)?Bush\b|"
    r"\b(?:President\s+)?(?:Bill\s+)?Clinton\b|\b(?:President\s+)?Obama\b|\b(?:President\s+)?Trump\b|"
    r"\b(?:President\s+)?Carter\b|\b(?:President\s+)?Nixon\b|\b(?:President\s+)?Ford\b|\bAmerica(?:n|ns)?\b",
    re.IGNORECASE,
)
NON_US_AMERICA_RE = re.compile(
    r"\b(?:Latin|Central|South|North|inter|Inter|Pan|pan|Ibero)[ -]American?s?\b|"
    r"\b(?:Latin|Central|South|North|Spanish) America\b|\bOrganization of American States\b|\bAmericas\b|"
    r"\bAmerican (?:continent|regional|hemisphere|republics?|countries|lands)\b|"
    r"\b(?:sister republics|peoples|nations) of America\b",
    re.IGNORECASE,
)
INDIRECT_RE = re.compile(
    r"\bNATO\b|North Atlantic Treaty Organization|\bWestern\b|\bthe West\b|"
    r"\bimperialis(?:m|t|ts|tic)\b|\bhegemon(?:y|ic|ism)\b|\bsuperpower(?:s)?\b|"
    r"\bBretton Woods\b|\bembargo\b|\bblockade\b|\bsanctions\b", re.IGNORECASE)

def paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n+|\n(?=\s*\d{1,3}[.)-]\s+)", text)
    return [re.sub(r"\s+", " ", c).strip() for c in chunks if c.strip()]

def direct_matches(paragraph: str):
    return list(DIRECT_RE.finditer(NON_US_AMERICA_RE.sub("", paragraph)))

def direct_hits(paragraph: str) -> list[str]:
    return [m.group(0) for m in direct_matches(paragraph)]

def direct_passage_count(paragraph: str) -> int:
    matches = direct_matches(paragraph)
    if not matches: return 0
    return 1 + sum(cur.start() - prev.end() > 700 for prev, cur in zip(matches, matches[1:]))

def compact_snippet(paragraph: str) -> str:
    matches = direct_matches(paragraph) or list(INDIRECT_RE.finditer(paragraph))
    windows = []
    for m in matches[:8]:
        snippet = paragraph[max(0,m.start()-350):min(len(paragraph),m.end()+550)]
        if snippet not in windows: windows.append(snippet)
    return " […] ".join(windows)[:6000]

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("start",type=int); ap.add_argument("end",type=int)
    ap.add_argument("--input",default="inputs/blinded_stance_validation_200.csv"); ap.add_argument("--compact",action="store_true")
    args=ap.parse_args()
    with Path(args.input).open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    for number,row in enumerate(rows,1):
        if not args.start<=number<=args.end: continue
        paras=paragraphs(row["analysis_text"]); relevant=[]; count=0
        for i,para in enumerate(paras):
            hits=direct_hits(para); indirect=bool(INDIRECT_RE.search(para)); count+=direct_passage_count(para)
            if hits or indirect:
                item={"paragraph":i+1,"direct_hits":hits,"indirect":indirect,"text":compact_snippet(para) if args.compact else para}
                if not args.compact:
                    item["previous"]=paras[i-1] if i else ""; item["next"]=paras[i+1] if i+1<len(paras) else ""
                relevant.append(item)
        print(json.dumps({"row":number,"review_id":row["review_id"],"iso3":row["iso3"],"year":row["year"],"direct_passages_auto":count,"relevant":relevant},ensure_ascii=False))
if __name__=="__main__": main()
