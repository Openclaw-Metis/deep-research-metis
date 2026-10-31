"""Claim extraction function group.

Splitting a report into claims is where English-only tooling usually breaks on
Traditional Chinese: a whole section collapses into one sentence because the
splitter only cuts on an ASCII period followed by a capital letter. This group
segments CJK and Latin prose with the same rules, keeps the citation markers
attached to the sentence that carries them, and skips structural lines that are
not claims at all. Table rows stay in scope because that is where comparison
reports keep their numbers.
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from research_store import (
    FENCE,
    HEADING,
    SemanticError,
    bilingual_length,
    citation_numbers,
    digest,
    find_bibliography,
    load_lexicon,
    quantity_values,
    read_report,
    resolve_run_dir,
    write_jsonl_atomic,
)

LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_DIVIDER = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
# A Latin stop ends a sentence only before whitespace or a citation, which leaves
# decimals, versions and domain names intact. Semicolons join clauses that share
# one trailing citation, so they do not end a sentence.
SENTENCE_END = re.compile(r"[。！？]|[.!?](?=\s|$|[\[［【])")
SENTENCE_TRAILER = re.compile(r"(?:[」』）)\"'”’]|\s*[\[［【][\d\s,，、;；\-–—~～]+[\]］】])*")
DOTTED_INITIALS = re.compile(r"(?:^|\s)(?:[A-Za-z]\.)+$")
ABBREVIATIONS = frozenset(
    {"al.", "approx.", "corp.", "dr.", "etc.", "fig.", "inc.", "ltd.", "mr.", "ms.", "no.", "prof.", "vs."}
)
PROCESS_MARKERS = tuple(load_lexicon("section_aliases")["process_section_markers"])
MIN_CLAIM_LENGTH = 6


def _ends_with_abbreviation(chunk: str) -> bool:
    words = chunk.split()
    return bool(DOTTED_INITIALS.search(chunk)) or (bool(words) and words[-1].lower() in ABBREVIATIONS)


def _split_sentences(paragraph: str) -> list[str]:
    parts: list[str] = []
    cursor = 0
    position = 0
    while True:
        match = SENTENCE_END.search(paragraph, position)
        if match is None:
            break
        position = match.end()
        if match.group(0) == "." and _ends_with_abbreviation(paragraph[cursor:position]):
            continue
        position = SENTENCE_TRAILER.match(paragraph, position).end()
        parts.append(paragraph[cursor:position].strip())
        cursor = position
    tail = paragraph[cursor:].strip()
    if tail:
        parts.append(tail)
    return [part for part in parts if part]


def _prose_blocks(report: str) -> Iterator[tuple[str, str, str]]:
    """Yield (section, text, origin), joining soft-wrapped lines into one paragraph."""
    _, bibliography = find_bibliography(report)
    lines = report.splitlines()
    section = "preamble"
    in_fence = False
    paragraph: list[str] = []

    def flush() -> Iterator[tuple[str, str, str]]:
        if paragraph:
            yield section, " ".join(paragraph), "prose"
            paragraph.clear()

    for index, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            yield from flush()
            continue
        if in_fence:
            continue
        heading = HEADING.match(line)
        if heading:
            yield from flush()
            section = heading.group(2).strip()
            continue
        stripped = line.strip()
        if index in bibliography or not stripped or stripped.startswith((">", "---", ":--", "![")):
            yield from flush()
            continue
        table_row = TABLE_ROW.match(line)
        if table_row:
            yield from flush()
            is_header = index + 1 < len(lines) and TABLE_DIVIDER.match(lines[index + 1])
            if not TABLE_DIVIDER.match(line) and not is_header:
                yield section, " ".join(cell.strip() for cell in table_row.group(1).split("|") if cell.strip()), "table"
            continue
        if LIST_MARKER.match(line):
            yield from flush()
        paragraph.append(LIST_MARKER.sub("", stripped))
    yield from flush()


def _claim_kind(sentence: str, section: str) -> str:
    if citation_numbers(sentence):
        return "cited"
    if any(marker in section.lower() for marker in PROCESS_MARKERS):
        return "process"
    return "quantitative-uncited" if quantity_values(sentence) else "qualitative"


def extract_claims(payload: dict[str, Any]) -> dict[str, Any]:
    """Segment report prose and table rows into claim records with citations, section, and kind."""
    run_dir = resolve_run_dir(payload)
    report = read_report(payload, run_dir)
    if not report.strip():
        raise SemanticError("claim.report-empty", "the report body is empty")

    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    report_digest = "sha256:" + digest(report)
    for section, text, origin in _prose_blocks(report):
        for sentence in ([text] if origin == "table" else _split_sentences(text)):
            kind = _claim_kind(sentence, section)
            if kind == "qualitative" and bilingual_length(sentence) < MIN_CLAIM_LENGTH:
                continue
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
                    "citations": citation_numbers(sentence),
                    "kind": kind,
                    "origin": origin,
                    "measured_length": bilingual_length(sentence),
                    "report_digest": report_digest,
                }
            )

    require_cited = payload.get("require_cited_claims", True)
    cited = [claim for claim in claims if claim["kind"] == "cited"]
    if require_cited and not cited:
        raise SemanticError("claim.no-cited-claim", "the report contains no cited factual claim")
    claims_path = run_dir / "claims.jsonl"
    write_jsonl_atomic(claims_path, claims)
    return {
        "status": "OK",
        "claims_path": str(claims_path),
        "report_digest": report_digest,
        "claims": claims,
        "counts": {
            "extracted": len(claims),
            "cited": len(cited),
            "quantitative_uncited": sum(1 for claim in claims if claim["kind"] == "quantitative-uncited"),
            "qualitative": sum(1 for claim in claims if claim["kind"] == "qualitative"),
            "process": sum(1 for claim in claims if claim["kind"] == "process"),
        },
    }
