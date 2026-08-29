"""Report verification function group.

Three checks run against a finished draft: the section contract, the citation
chain, and claim-level support. All three are bilingual by construction —
headings match on Traditional Chinese or English aliases, length is measured in
CJK characters as well as Latin words, and claim support is scored on CJK
bigrams as well as Latin tokens.
"""

from __future__ import annotations

import json
import re
from typing import Any

from research_store import (
    SemanticError,
    bilingual_length,
    canonical_url,
    read_jsonl,
    load_lexicon,
    read_report,
    resolve_run_dir,
    support_score,
    write_json_atomic,
)

HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")
CITATION = re.compile(r"\[(\d{1,3})\]")
URL = re.compile(r"https?://[^\s)\]|>]+")
LEXICON = load_lexicon("section_aliases")
SECTION_ALIASES = {key: tuple(value) for key, value in LEXICON["sections"].items()}
PLACEHOLDER = re.compile("|".join(re.escape(marker) for marker in LEXICON["placeholder_markers"]), re.IGNORECASE)
SUPPORTED_THRESHOLD = 0.45
PARTIAL_THRESHOLD = 0.22
CROSS_SCRIPT_SUPPORTED = 0.60
CROSS_SCRIPT_PARTIAL = 0.34


def _finding(severity: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    record = {"severity": severity, "code": code, "message": message}
    record.update(extra)
    return record


def _status(findings: list[dict[str, Any]]) -> str:
    return "FAIL" if any(item["severity"] == "error" for item in findings) else "PASS"


def _optional_run_dir(payload: dict[str, Any]):
    return resolve_run_dir(payload, create=False) if payload.get("run_dir") else None


def _headings(report: str) -> list[str]:
    found = []
    in_fence = False
    for line in report.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match:
            found.append(match.group(1).strip())
    return found


def check_structure(payload: dict[str, Any]) -> dict[str, Any]:
    """Verify required sections, bilingual headings, placeholders, and minimum depth."""
    run_dir = _optional_run_dir(payload)
    report = read_report(payload, run_dir)
    required = payload.get("required_sections") or list(SECTION_ALIASES)
    unknown = [key for key in required if key not in SECTION_ALIASES]
    if unknown:
        raise SemanticError("structure.section-key-unknown", "unknown required section key: " + ", ".join(unknown))

    headings = _headings(report)
    lowered = [heading.lower() for heading in headings]
    findings: list[dict[str, Any]] = []
    present: list[str] = []
    for key in required:
        aliases = SECTION_ALIASES[key]
        if any(alias in heading for heading in lowered for alias in aliases):
            present.append(key)
        else:
            findings.append(
                _finding("error", "section_missing", "缺少必要章節：" + key, section=key, accepted_aliases=list(aliases))
            )
    for line_number, line in enumerate(report.splitlines(), start=1):
        if PLACEHOLDER.search(line):
            findings.append(_finding("error", "placeholder_present", "報告仍保留佔位字串", line=line_number))
    measured = bilingual_length(report)
    minimum = int(payload.get("min_length", 0))
    if minimum and measured < minimum:
        findings.append(
            _finding("error", "report_too_short", "報告長度不足", measured_length=measured, min_length=minimum)
        )
    if not CITATION.search(report):
        findings.append(_finding("error", "no_inline_citation", "報告沒有任何行內引用標記"))

    return {
        "status": _status(findings),
        "sections_present": present,
        "sections_required": required,
        "headings": headings,
        "measured_length": measured,
        "findings": findings,
    }


def _bibliography_lines(report: str) -> list[str]:
    lines: list[str] = []
    capturing = False
    for line in report.splitlines():
        match = HEADING.match(line)
        if match:
            capturing = any(alias in match.group(1).lower() for alias in SECTION_ALIASES["bibliography"])
            continue
        if capturing and line.strip():
            lines.append(line.strip())
    return lines


def check_citations(payload: dict[str, Any]) -> dict[str, Any]:
    """Match inline markers to bibliography entries and bind each entry to a registered source."""
    run_dir = resolve_run_dir(payload, create=False)
    report = read_report(payload, run_dir)
    sources = read_jsonl(run_dir / "sources.jsonl")
    if not sources:
        raise SemanticError("citation.sources-not-registered", "sources.jsonl is empty; register sources first")
    by_canonical = {record["canonical_url"]: record for record in sources}

    inline = sorted({int(number) for number in CITATION.findall(report)})
    findings: list[dict[str, Any]] = []
    citation_map: dict[str, str] = {}
    entry_numbers: list[int] = []
    for line in _bibliography_lines(report):
        numbers = CITATION.findall(line)
        if not numbers:
            continue
        number = int(numbers[0])
        entry_numbers.append(number)
        if PLACEHOLDER.search(line):
            findings.append(_finding("error", "bibliography_placeholder", "參考來源仍是佔位項目", entry=number))
            continue
        url_match = URL.search(line)
        if not url_match:
            findings.append(_finding("error", "bibliography_entry_without_url", "參考來源缺少可追溯連結", entry=number))
            continue
        url = url_match.group(0).rstrip(".,;")
        try:
            record = by_canonical.get(canonical_url(url))
        except SemanticError:
            record = None
        if record is None:
            findings.append(
                _finding("error", "source_not_registered", "參考來源未登錄於 source ledger", entry=number, url=url)
            )
            continue
        citation_map[str(number)] = record["source_id"]

    duplicates = sorted({number for number in entry_numbers if entry_numbers.count(number) > 1})
    for number in duplicates:
        findings.append(_finding("error", "duplicate_bibliography_entry", "參考來源編號重複", entry=number))
    for number in inline:
        if number not in entry_numbers:
            findings.append(_finding("error", "citation_without_entry", "行內引用沒有對應的參考來源", citation=number))
    for number in sorted(set(entry_numbers)):
        if number not in inline:
            findings.append(_finding("warning", "entry_without_citation", "參考來源沒有被任何主張引用", entry=number))

    map_path = run_dir / "citation_map.json"
    write_json_atomic(map_path, {"citation_map": citation_map, "inline_citations": inline})
    return {
        "status": _status(findings),
        "citation_map_path": str(map_path),
        "citation_map": citation_map,
        "counts": {
            "inline_citations": len(inline),
            "bibliography_entries": len(set(entry_numbers)),
            "resolved_sources": len(citation_map),
        },
        "findings": findings,
    }


def check_claim_support(payload: dict[str, Any]) -> dict[str, Any]:
    """Score every cited claim against the persisted evidence of the source it cites."""
    run_dir = resolve_run_dir(payload, create=False)
    claims = read_jsonl(run_dir / "claims.jsonl")
    if not claims:
        raise SemanticError("support.claims-missing", "claims.jsonl is empty; extract claims first")
    evidence = read_jsonl(run_dir / "evidence.jsonl")
    if not evidence:
        raise SemanticError("support.evidence-missing", "evidence.jsonl is empty; persist evidence first")
    map_path = run_dir / "citation_map.json"
    if not map_path.is_file():
        raise SemanticError("support.citation-map-missing", "run check_citations before scoring claim support")
    citation_map = json.loads(map_path.read_text(encoding="utf-8")).get("citation_map")
    if not isinstance(citation_map, dict) or not citation_map:
        raise SemanticError("support.citation-map-empty", "citation_map.json holds no resolved citation")

    quotes_by_source: dict[str, list[dict[str, Any]]] = {}
    for record in evidence:
        quotes_by_source.setdefault(record["source_id"], []).append(record)

    supported_threshold = float(payload.get("supported_threshold", SUPPORTED_THRESHOLD))
    partial_threshold = float(payload.get("partial_threshold", PARTIAL_THRESHOLD))
    if not 0 < partial_threshold < supported_threshold <= 1:
        raise SemanticError("support.threshold-invalid", "thresholds must satisfy 0 < partial < supported <= 1")

    scored: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for claim in claims:
        if claim["kind"] == "quantitative-uncited":
            findings.append(
                _finding("error", "quantitative_claim_uncited", "含數據的主張沒有引用", claim_id=claim["claim_id"])
            )
            continue
        if claim["kind"] != "cited":
            continue
        best_score = 0.0
        best_evidence = None
        best_method = "no-evidence"
        for number in claim["citations"]:
            source_id = citation_map.get(str(number))
            if source_id is None:
                findings.append(
                    _finding(
                        "error",
                        "citation_unresolved",
                        "引用編號無法對應到來源",
                        claim_id=claim["claim_id"],
                        citation=number,
                    )
                )
                continue
            for record in quotes_by_source.get(source_id, []):
                score, method = support_score(claim["text"], record["quote"])
                if score > best_score or best_evidence is None:
                    best_score = max(score, best_score)
                    best_evidence = record["evidence_id"]
                    best_method = method
        if best_method == "cross-script-anchor":
            supported_at, partial_at = CROSS_SCRIPT_SUPPORTED, CROSS_SCRIPT_PARTIAL
        else:
            supported_at, partial_at = supported_threshold, partial_threshold
        if best_method == "insufficient-signal":
            verdict = "unverifiable"
            findings.append(
                _finding(
                    "error" if payload.get("require_cross_language_anchor", False) else "warning",
                    "cross_language_claim_unverifiable",
                    "跨語言主張沒有數字或專有名詞可供比對，請補上可對照的錨點或同語言引文",
                    claim_id=claim["claim_id"],
                )
            )
        elif best_score >= supported_at:
            verdict = "supported"
        elif best_score >= partial_at:
            verdict = "partial"
        else:
            verdict = "unsupported"
            findings.append(
                _finding(
                    "error" if payload.get("strict", True) else "warning",
                    "claim_unsupported",
                    "主張與已持久化證據的重疊度過低",
                    claim_id=claim["claim_id"],
                    score=best_score,
                    method=best_method,
                )
            )
        scored.append(
            {
                "claim_id": claim["claim_id"],
                "verdict": verdict,
                "score": best_score,
                "method": best_method,
                "best_evidence_id": best_evidence,
                "citations": claim["citations"],
            }
        )

    summary = {
        "scored": len(scored),
        "supported": sum(1 for item in scored if item["verdict"] == "supported"),
        "partial": sum(1 for item in scored if item["verdict"] == "partial"),
        "unsupported": sum(1 for item in scored if item["verdict"] == "unsupported"),
        "unverifiable": sum(1 for item in scored if item["verdict"] == "unverifiable"),
        "cross_script_scored": sum(1 for item in scored if item["method"] == "cross-script-anchor"),
        "supported_threshold": supported_threshold,
        "partial_threshold": partial_threshold,
        "cross_script_supported_threshold": CROSS_SCRIPT_SUPPORTED,
    }
    report_path = run_dir / "claim_support.json"
    write_json_atomic(report_path, {"summary": summary, "claims": scored, "findings": findings})
    return {"status": _status(findings), "report_path": str(report_path), "summary": summary, "claims": scored, "findings": findings}
