"""Shared run-workspace helpers for the deep research report domain.

All functions in this skill persist artifacts inside one caller-declared run
directory. This module owns path resolution, the workspace boundary check,
stable identifiers, append-only JSONL access, and the bilingual text measures
used by the verification functions.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib import parse as urlparse

SKILL_ROOT = Path(__file__).resolve().parents[1]

CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x3040, 0x30FF),
    (0xAC00, 0xD7AF),
)
LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]*|\d+(?:[.,]\d+)*%?")
NUMBER_TOKEN = re.compile(r"\d+(?:[.,]\d+)*\s?(?:%|percent|億|萬|兆|kwh|gw|mw|tw)?", re.IGNORECASE)
PROPER_NOUN = re.compile(r"\b(?:[A-Z]{2,}|[A-Z][a-z]{2,})\b")
CITATION_MARK = re.compile(r"\[\d{1,3}\]")
SECRET_QUERY_PARAMS = frozenset(
    {"api_key", "apikey", "key", "token", "access_token", "auth", "signature", "sig", "password"}
)
TRACKING_PARAMS = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src", "spm",
    }
)


class SemanticError(Exception):
    """Raised when a domain invariant fails; carries the failed rule id."""

    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(payload: dict[str, Any], key: str, rule_id: str) -> Any:
    value = payload.get(key)
    if value is None or (isinstance(value, (str, list, dict)) and len(value) == 0):
        raise SemanticError(rule_id, f"payload.{key} is required and must be non-empty")
    return value


def resolve_run_dir(payload: dict[str, Any], *, create: bool = True) -> Path:
    """Resolve the run workspace and keep mutable state outside the skill folder."""
    raw = require(payload, "run_dir", "workspace.run-dir-required")
    if not isinstance(raw, str):
        raise SemanticError("workspace.run-dir-required", "run_dir must be a string path")
    run_dir = Path(raw).expanduser()
    if not run_dir.is_absolute():
        run_dir = (Path.cwd() / run_dir).resolve()
    else:
        run_dir = run_dir.resolve()
    if run_dir == SKILL_ROOT or SKILL_ROOT in run_dir.parents:
        raise SemanticError(
            "workspace.outside-skill-root",
            "run_dir must stay outside the skill folder so the skill holds no mutable state",
        )
    if create:
        run_dir.mkdir(parents=True, exist_ok=True)
    elif not run_dir.is_dir():
        raise SemanticError("workspace.run-dir-missing", f"run_dir does not exist: {run_dir}")
    return run_dir


def resolve_inside(run_dir: Path, relative: str, rule_id: str) -> Path:
    """Resolve a caller-supplied path and reject anything escaping the run workspace."""
    candidate = Path(relative).expanduser()
    candidate = (run_dir / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if run_dir != candidate and run_dir not in candidate.parents:
        raise SemanticError(rule_id, f"path escapes the run workspace: {relative}")
    return candidate


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    """Append records without rewriting history; the ledgers stay append-only."""
    payload = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    if not payload:
        return 0
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return payload.count("\n")


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write through a temporary file and commit atomically to survive interruption."""
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp_path, path)


def read_report(payload: dict[str, Any], run_dir: Path | None) -> str:
    """Accept inline markdown or a path inside the run workspace, never both empty."""
    inline = payload.get("report_markdown")
    if isinstance(inline, str) and inline.strip():
        return inline
    report_path = payload.get("report_path")
    if isinstance(report_path, str) and report_path.strip():
        if run_dir is None:
            raise SemanticError("report.workspace-required", "report_path needs a run_dir workspace")
        resolved = resolve_inside(run_dir, report_path, "report.path-inside-workspace")
        if not resolved.is_file():
            raise SemanticError("report.path-missing", f"report file not found: {report_path}")
        return resolved.read_text(encoding="utf-8")
    raise SemanticError("report.source-required", "provide report_markdown or report_path")


def canonical_url(url: str) -> str:
    """Normalise a URL so the same source keeps one stable identity across runs."""
    parts = urlparse.urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        raise SemanticError("source.url-invalid", f"source url must be absolute: {url}")
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = [
        (key, value)
        for key, value in urlparse.parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS and key.lower() not in SECRET_QUERY_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlparse.urlunsplit((parts.scheme.lower(), netloc, path, urlparse.urlencode(sorted(query)), ""))


def stripped_credentials(url: str) -> list[str]:
    """Report which credential-like query parameters were removed from a source URL.

    A search or API endpoint often carries a key in the query string. Persisting
    it would leak the credential into the ledger and into every rendered
    bibliography, so canonicalisation drops it and the caller records that the
    removal happened.
    """
    try:
        parts = urlparse.urlsplit(url.strip())
    except ValueError:
        return []
    return sorted(
        {key for key, _ in urlparse.parse_qsl(parts.query, keep_blank_values=True) if key.lower() in SECRET_QUERY_PARAMS}
    )


def is_cjk(char: str) -> bool:
    code = ord(char)
    return any(start <= code <= end for start, end in CJK_RANGES)


def bilingual_length(text: str) -> int:
    """Count CJK characters individually and Latin runs as words."""
    cjk = sum(1 for char in text if is_cjk(char))
    latin = len(LATIN_TOKEN.findall(text))
    return cjk + latin


def load_lexicon(name: str) -> dict[str, Any]:
    """Load a bundled lexicon from assets/ using a script-relative path.

    Resolving from the module file rather than the process working directory is
    what lets the same call work from any shell location, and it keeps the
    bilingual alias table as data instead of hard-coded literals.
    """
    path = SKILL_ROOT / "assets" / "lexicon" / (name + ".json")
    if not path.is_file():
        raise SemanticError("lexicon.asset-missing", "bundled lexicon is missing: " + name)
    return json.loads(path.read_text(encoding="utf-8"))


def strip_citation_marks(text: str) -> str:
    """Remove inline citation markers so numbering never counts as claim content."""
    return CITATION_MARK.sub(" ", text)


def normalize_for_match(text: str) -> str:
    folded = unicodedata.normalize("NFKC", strip_citation_marks(text)).lower()
    return re.sub(r"\s+", " ", folded).strip()


def latin_tokens(text: str) -> set[str]:
    return {token.lower() for token in LATIN_TOKEN.findall(normalize_for_match(text)) if len(token) > 1}


def cjk_bigrams(text: str) -> set[str]:
    chars = [char for char in normalize_for_match(text) if is_cjk(char)]
    return {"".join(chars[index:index + 2]) for index in range(len(chars) - 1)}


def dominant_script(text: str) -> str:
    """Return the script a sentence is written in, so scoring compares like with like."""
    cjk = sum(1 for char in text if is_cjk(char))
    latin = len(LATIN_TOKEN.findall(text))
    return "cjk" if cjk >= latin else "latin"


def anchor_tokens(text: str) -> set[str]:
    """Collect the cross-language checkable anchors: numbers, units, acronyms, proper nouns."""
    normalized = unicodedata.normalize("NFKC", strip_citation_marks(text))
    anchors = {match.group(0).lower().replace(" ", "") for match in NUMBER_TOKEN.finditer(normalized)}
    anchors.update(match.group(0).lower() for match in PROPER_NOUN.finditer(normalized))
    return {anchor for anchor in anchors if anchor}


def overlap_score(claim: str, evidence: str) -> float:
    """Score same-script lexical coverage of the claim by the evidence quote."""
    if dominant_script(claim) == "cjk":
        claim_units, evidence_units = cjk_bigrams(claim), cjk_bigrams(evidence)
    else:
        claim_units, evidence_units = latin_tokens(claim), latin_tokens(evidence)
    if not claim_units:
        return 0.0
    return round(len(claim_units & evidence_units) / len(claim_units), 4)


def support_score(claim: str, evidence: str) -> tuple[float, str]:
    """Score a claim against one quote and report which method produced the score.

    Same-script pairs are scored on lexical coverage. A Traditional Chinese claim
    citing an English quote cannot be scored that way at all, which is why
    English-only verifiers mark every such claim unsupported. Those pairs are
    scored on the anchors that do survive translation - numbers, units, acronyms
    and proper nouns - and a claim carrying no anchor is reported as unverifiable
    rather than silently failed.
    """
    if dominant_script(claim) == dominant_script(evidence):
        return overlap_score(claim, evidence), "same-script-lexical"
    claim_anchors = anchor_tokens(claim)
    if not claim_anchors:
        return 0.0, "insufficient-signal"
    evidence_anchors = anchor_tokens(evidence)
    return round(len(claim_anchors & evidence_anchors) / len(claim_anchors), 4), "cross-script-anchor"
