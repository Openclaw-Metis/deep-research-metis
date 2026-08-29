"""Claim extraction function group.

Splitting a report into claims is where English-only tooling usually breaks on
Traditional Chinese: a whole section collapses into one sentence because the
splitter only cuts on an ASCII period followed by a capital letter. This group
segments CJK and Latin prose with the same rules, keeps the citation markers
attached to the sentence that carries them, and skips structural lines that are
not claims at all.
"""

from __future__ import annotations

import re
from typing import Any

from research_store import (
    SemanticError,
    append_jsonl,
    bilingual_length,
    digest,
    load_lexicon,
    read_jsonl,
    read_report,
    require,
    resolve_run_dir,
)

HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")
LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
CITATION = re.compile(r"\[(\d{1,3})\]")
SENTENCE_BREAK = re.compile(r"(?<=[。！？；?!.])(?:\s*\[\d{1,3}\])*\s*")
NUMERIC = re.compile(r"\d")
BIBLIOGRAPHY_ALIASES = tuple(load_lexicon("section_aliases")["sections"]["bibliography"])
MIN_CLAIM_LENGTH = 6


def _section_key(heading: str) -> str:
    lowered = heading.strip().lower()
    for alias in BIBLIOGRAPHY_ALIASES:
        if alias in lowered:
            return "bibliography"
    return heading.strip()


def _split_sentences(paragraph: str) -> list[str]:
    parts: list[str] = []
    cursor = 0
    for match in SENTENCE_BREAK.finditer(paragraph):
        chunk = paragraph[cursor:match.end()].strip()
        if chunk:
            parts.append(chunk)
        cursor = match.end()
    tail = paragraph[cursor:].strip()
    if tail:
        parts.append(tail)
    return parts


def extract_claims(payload: dict[str, Any]) -> dict[str, Any]:
    """Segment report prose into claim records with citations, section, and kind."""
    run_dir = resolve_run_dir(payload)
    report = read_report(payload, run_dir)
    if not report.strip():
        raise SemanticError("claim.report-empty", "the report body is empty")

    section = "preamble"
    in_fence = False
    claims: list[dict[str, Any]] = []
    seen: set[str] = {record["claim_hash"] for record in read_jsonl(run_dir / "claims.jsonl")}
    for line in report.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING.match(line)
        if heading:
            section = _section_key(heading.group(1))
            continue
        if section == "bibliography":
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(("|", ">", "---", ":--")):
            continue
        body = LIST_MARKER.sub("", stripped)
        for sentence in _split_sentences(body):
            if bilingual_length(sentence) < MIN_CLAIM_LENGTH:
                continue
            citations = sorted({int(number) for number in CITATION.findall(sentence)})
            if citations:
                kind = "cited"
            elif NUMERIC.search(sentence):
                kind = "quantitative-uncited"
            else:
                kind = "qualitative"
            claim_hash = digest(section + "|" + sentence)
            if claim_hash in seen:
                continue
            seen.add(claim_hash)
            claims.append(
                {
                    "claim_id": "C" + claim_hash[:10],
                    "claim_hash": claim_hash,
                    "section": section,
                    "text": sentence,
                    "citations": citations,
                    "kind": kind,
                    "measured_length": bilingual_length(sentence),
                }
            )

    claims_path = run_dir / "claims.jsonl"
    append_jsonl(claims_path, claims)
    require_cited = payload.get("require_cited_claims", True)
    cited = [claim for claim in claims if claim["kind"] == "cited"]
    if require_cited and claims and not cited:
        raise SemanticError("claim.no-cited-claim", "the report contains no cited factual claim")
    return {
        "status": "OK",
        "claims_path": str(claims_path),
        "claims": claims,
        "counts": {
            "extracted": len(claims),
            "cited": len(cited),
            "quantitative_uncited": sum(1 for claim in claims if claim["kind"] == "quantitative-uncited"),
            "qualitative": sum(1 for claim in claims if claim["kind"] == "qualitative"),
        },
    }
