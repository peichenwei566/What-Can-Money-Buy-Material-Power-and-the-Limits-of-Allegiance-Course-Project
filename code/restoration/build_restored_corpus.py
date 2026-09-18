#!/usr/bin/env python3
"""Build an analysis corpus using only defensible automatic speech replacements."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00ad", "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def common_prefix_ratio(supplied: str, candidate: str) -> float:
    supplied_n = normalize(supplied)
    candidate_n = normalize(candidate)
    limit = min(len(supplied_n), len(candidate_n))
    index = 0
    while index < limit and supplied_n[index] == candidate_n[index]:
        index += 1
    return index / max(1, len(supplied_n))


def inspect_candidate(supplied: str, path: Path) -> dict:
    full_text = path.read_text(encoding="utf-8", errors="replace")
    exact = full_text.startswith(supplied)
    normalized = normalize(full_text).startswith(normalize(supplied))
    ratio = common_prefix_ratio(supplied, full_text)
    if len(full_text) < len(supplied):
        status = "rejected-shorter-than-supplied"
    elif exact:
        status = "exact-prefix"
    elif normalized:
        status = "normalized-prefix"
    elif ratio >= 0.98:
        status = "manual-review-strong-fuzzy"
    else:
        status = "rejected-mismatch"
    return {
        "path": path,
        "text": full_text,
        "status": status,
        "match_score": ratio,
        "sha256": hash_text(full_text),
    }


def candidates(corpus_root: Path, iso3: str, year: int) -> list[Path]:
    pattern = re.compile(rf"^{re.escape(iso3)}_(\d+)_{year}\.txt$", re.IGNORECASE)
    return sorted(path for path in corpus_root.rglob("*.txt") if pattern.match(path.name))


def original_root(path: Path) -> Path | None:
    """Return a data/original ancestor when one exists."""
    resolved = path.resolve()
    for ancestor in (resolved, *resolved.parents):
        if ancestor.name == "original" and ancestor.parent.name == "data":
            return ancestor
    return None


def validate_destinations(
    source: Path, corpus_root: Path, output: Path, manifest: Path, review: Path
) -> None:
    protected = {root for root in (original_root(source), original_root(corpus_root)) if root}
    project_roots = {root.parent.parent for root in protected}
    if len(project_roots) != 1:
        raise ValueError("Inputs must resolve to one Project_3 data/original tree")
    project_root = project_roots.pop()
    resolved_destinations = [output.resolve(), manifest.resolve(), review.resolve()]
    if len(set(resolved_destinations)) != len(resolved_destinations):
        raise ValueError("Output, manifest, and review paths must be distinct")
    for destination in resolved_destinations:
        if any(destination == root or root in destination.parents for root in protected):
            raise ValueError(f"Refusing to write inside immutable original data: {destination}")
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite an existing artifact: {destination}")
    allowed = {
        output.resolve(): project_root / "data" / "processed",
        manifest.resolve(): project_root / "manifests",
        review.resolve(): project_root / "data" / "interim",
    }
    for destination, allowed_root in allowed.items():
        if destination != allowed_root and allowed_root not in destination.parents:
            raise ValueError(f"Artifact must be written under {allowed_root}: {destination}")


def build(args: argparse.Namespace) -> None:
    supplied_path = Path(args.supplied).resolve()
    corpus_root = Path(args.corpus_root).resolve()
    output = Path(args.output).resolve()
    manifest = Path(args.manifest).resolve()
    review = Path(args.review).resolve()
    validate_destinations(supplied_path, corpus_root, output, manifest, review)
    source = pd.read_parquet(supplied_path)
    records = []
    output_rows = []

    for row in source.to_dict("records"):
        supplied = str(row["text"])
        iso3 = str(row["iso3"]).upper()
        year = int(row["year"])
        was_truncated = bool(row["truncated"])
        record = {
            "iso3": iso3,
            "country": row.get("country"),
            "year": year,
            "was_truncated": was_truncated,
            "provided_sha256": hash_text(supplied),
            "candidate_count": 0,
            "candidate_paths": [],
            "replacement_status": "not-truncated",
            "match_score": 1.0,
            "full_text_sha256": hash_text(supplied),
            "source_path": None,
        }
        analysis_text = supplied
        full_text = supplied if not was_truncated else None
        complete = not was_truncated

        if was_truncated:
            found = candidates(corpus_root, iso3, year)
            record["candidate_count"] = len(found)
            record["candidate_paths"] = [str(path.relative_to(corpus_root)) for path in found]
            if not found:
                record["replacement_status"] = "missing"
                record["match_score"] = 0.0
                record["full_text_sha256"] = None
            elif len(found) > 1:
                checks = [inspect_candidate(supplied, path) for path in found]
                record["replacement_status"] = "ambiguous-multiple-candidates"
                record["match_score"] = max(check["match_score"] for check in checks)
                record["full_text_sha256"] = None
            else:
                check = inspect_candidate(supplied, found[0])
                record["replacement_status"] = check["status"]
                record["match_score"] = check["match_score"]
                record["full_text_sha256"] = check["sha256"]
                record["source_path"] = str(found[0].relative_to(corpus_root))
                if check["status"] in {"exact-prefix", "normalized-prefix"}:
                    full_text = check["text"]
                    analysis_text = check["text"]
                    complete = True

        output_row = dict(row)
        output_row.update(
            {
                "text_provided": supplied,
                "text_full": full_text,
                "analysis_text": analysis_text,
                "was_truncated": was_truncated,
                "replacement_status": record["replacement_status"],
                "analysis_text_complete": complete,
                "source_provider": "UN General Debate Corpus",
                "source_path": record["source_path"],
                "provided_sha256": record["provided_sha256"],
                "full_text_sha256": record["full_text_sha256"],
                "match_method": record["replacement_status"],
                "match_score": record["match_score"],
                "manual_review": record["replacement_status"] not in {
                    "not-truncated",
                    "exact-prefix",
                    "normalized-prefix",
                },
            }
        )
        records.append(record)
        output_rows.append(output_row)

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    review.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output_rows).to_parquet(output, index=False)
    with manifest.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    review_frame = pd.DataFrame(records)
    review_frame = review_frame[
        ~review_frame["replacement_status"].isin(
            ["not-truncated", "exact-prefix", "normalized-prefix"]
        )
    ]
    review_frame.to_csv(review, index=False)

    counts = pd.Series([record["replacement_status"] for record in records]).value_counts()
    print(counts.to_string())
    print(f"output={output}")
    print(f"manifest={manifest}")
    print(f"manual_review={review}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--supplied", required=True)
    parser.add_argument("--corpus-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--review", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
