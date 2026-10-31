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
# Accepts [1], [1, 2], [1-3], [1][2] and the full-width bracket forms zh-TW drafts use.
CITATION_MARK = re.compile(r"[\[［【]\s*(\d{1,3}(?:\s*[,，、;；\-–—~～]\s*\d{1,3})*)\s*[\]］】]")
CITATION_LIST_SPLIT = re.compile(r"[,，、;；]")
MAX_CITATION_RANGE = 50
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")
URL = re.compile(r"https?://[^\s)\]|>）］】」』〉》，。；、]+")
BIBLIOGRAPHY_ENTRY = re.compile(r"^\s*(?:[-*+]\s+)?(?:[\[［【]\s*(\d{1,3})\s*[\]］】]|(\d{1,3})[.)、])\s*\S")
# Years, ordinals and cross-references carry digits without asserting a quantity.
NON_QUANTITY = re.compile(
    r"(?<![\d.,])(?:19|20)\d{2}(?![\d.,]|\s*(?:%|％|percent|[kmgt]w|[kmgt]wh|tons?|萬|億|兆|千|百|個|家|座|台|件|噸|度|元))"
    r"|第\s*\d+|(?:表|圖|節|章|附錄)\s*\d+"
    r"|\b(?:table|figure|fig\.?|section|chapter|appendix)\s*\d+",
    re.IGNORECASE,
)
QUANTITY = re.compile(r"(?<![A-Za-z\d.,])\d+(?:,\d{3})*(?:\.\d+)?")
HEDGE_WORDS = re.compile(
    r"約|(?<![最附鄰])近(?![年期來日況])|逾|超過|左右|上下|\b(?:about|around|approximately|approx|roughly|nearly|almost|over|more than)\b|[~～≈]",
    re.IGNORECASE,
)
HEDGED_TOLERANCE = 0.05
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


def write_jsonl_atomic(path: Path, records: Iterable[dict[str, Any]]) -> int:
    """Replace a derived JSONL snapshot atomically.

    Source and evidence ledgers are append-only, but derived artifacts such as
    claims must represent exactly one report revision. Replacing those files
    prevents resumed verification from mixing stale and current claims.
    """
    payload = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temp_path, path)
    return payload.count("\n")


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write through a temporary file and commit atomically to survive interruption."""
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp_path, path)


def write_text_atomic(path: Path, text: str) -> None:
    """Atomically replace a text artifact after all validation has passed."""
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(text, encoding="utf-8", newline="\n")
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
    raw = url.strip()
    if any(ord(char) < 32 for char in raw):
        raise SemanticError("source.url-invalid", "source url contains control characters")
    try:
        parts = urlparse.urlsplit(raw)
        port = parts.port
    except ValueError as exc:
        raise SemanticError("source.url-invalid", f"source url is invalid: {url}") from exc
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise SemanticError("source.url-invalid", f"source url must be absolute: {url}")
    if parts.username is not None or parts.password is not None:
        raise SemanticError("source.url-credentials", "source url must not contain userinfo credentials")
    host = parts.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    default_port = (parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)
    netloc = host if port is None or default_port else host + ":" + str(port)
    query = [
        (key, value)
        for key, value in urlparse.parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS and key.lower() not in SECRET_QUERY_PARAMS
    ]
    # A browser copy gives percent-escapes while a typed bibliography keeps the
    # CJK text; both must resolve to the same source identity.
    path = urlparse.quote(parts.path.rstrip("/") or "/", safe="/%:@!$&'()*+,;=~-._")
    path = re.sub(r"%[0-9a-fA-F]{2}", lambda match: match.group(0).upper(), path)
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


def citation_numbers(text: str) -> list[int]:
    """Expand every citation form in the text into sorted reference numbers."""
    numbers: set[int] = set()
    for match in CITATION_MARK.finditer(text):
        for part in CITATION_LIST_SPLIT.split(match.group(1)):
            bounds = [int(value) for value in re.findall(r"\d+", part)]
            if len(bounds) == 2 and 0 <= bounds[1] - bounds[0] <= MAX_CITATION_RANGE:
                numbers.update(range(bounds[0], bounds[1] + 1))
            else:
                numbers.update(bounds)
    return sorted(numbers)


def strip_citation_marks(text: str) -> str:
    """Remove inline citation markers so numbering never counts as claim content."""
    return CITATION_MARK.sub(" ", text)


def _heading_spans(report: str) -> tuple[list[str], list[tuple[int, int, str]]]:
    """Return the report lines and each heading as (index, level, title), skipping code fences."""
    lines = report.splitlines()
    spans: list[tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            match = HEADING.match(line)
            if match:
                spans.append((index, len(match.group(1)), match.group(2).strip()))
    return lines, spans


def is_bibliography_entry(line: str) -> bool:
    return bool(URL.search(line) or BIBLIOGRAPHY_ENTRY.match(line))


def bibliography_entry_number(line: str) -> int | None:
    """Read the entry number from a `[1] ...` or numbered-list bibliography line."""
    match = BIBLIOGRAPHY_ENTRY.match(line)
    if match is None:
        return None
    return int(match.group(1) or match.group(2))


def find_bibliography(report: str) -> tuple[list[str], set[int]]:
    """Locate bibliography sections, returning their titles and 0-based line indexes.

    A heading alias alone is not enough. "資料來源比較" and "Sources of Uncertainty"
    are body sections, and treating them as a bibliography would exempt their
    claims from verification without anyone noticing, so a section counts only
    when most of its lines read as entries.
    """
    aliases = tuple(load_lexicon("section_aliases")["sections"]["bibliography"])
    lines, spans = _heading_spans(report)
    heading_indexes = {index for index, _, _ in spans}
    titles: list[str] = []
    entry_lines: set[int] = set()
    for position, (start, level, title) in enumerate(spans):
        if not any(alias in title.lower() for alias in aliases):
            continue
        end = next((index for index, other, _ in spans[position + 1:] if other <= level), len(lines))
        body = [
            index for index in range(start + 1, end)
            if lines[index].strip() and index not in heading_indexes and not FENCE.match(lines[index])
        ]
        if body and sum(is_bibliography_entry(lines[index]) for index in body) * 2 >= len(body):
            titles.append(title)
            entry_lines.update(body)
    return titles, entry_lines


def _numbers_in(text: str) -> list[float]:
    return [float(match.group(0).replace(",", "")) for match in QUANTITY.finditer(text)]


def quantity_values(text: str) -> list[float]:
    """Extract the numbers a sentence asserts, leaving out years and cross-references."""
    normalized = unicodedata.normalize("NFKC", strip_citation_marks(text))
    return _numbers_in(NON_QUANTITY.sub(" ", normalized))


def unmatched_quantities(claim: str, quotes: Iterable[str]) -> list[float]:
    """List claim numbers absent from every quote the claim cites.

    Lexical coverage cannot see a changed digit, so "成長 81%" scores as high as
    "成長 18%" against the same quote. A hedged claim ("約 12%") may round, within
    a tolerance narrow enough that "about 30%" still fails against 18%.
    """
    available = [
        value
        for quote in quotes
        for value in _numbers_in(unicodedata.normalize("NFKC", strip_citation_marks(quote)))
    ]
    hedged = bool(HEDGE_WORDS.search(claim))
    missing: list[float] = []
    for value in quantity_values(claim):
        tolerance = abs(value) * HEDGED_TOLERANCE if hedged else 1e-9
        if not any(abs(value - known) <= tolerance for known in available):
            missing.append(value)
    return missing


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
