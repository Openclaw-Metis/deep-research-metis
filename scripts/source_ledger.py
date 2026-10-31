"""Source identity function group.

Sources are the only place a run assigns stable identity. Registration
normalises the URL, derives a deterministic source id, merges duplicates, and
records soft authority signals that inform the reader without ever blocking a
run on perceived prestige.
"""

from __future__ import annotations

import re
from typing import Any

from research_store import (
    SemanticError,
    append_jsonl,
    canonical_url,
    digest,
    now_utc,
    read_jsonl,
    require,
    resolve_run_dir,
    stripped_credentials,
)

PRIMARY_DOMAINS = ("doi.org", "arxiv.org", "who.int", "oecd.org", "europa.eu")
PRIMARY_TLD = re.compile(r"(?:^|\.)(?:gov|edu)(?:\.[a-z]{2})?$")
COMMUNITY_DOMAINS = ("medium.com", "substack.com", "reddit.com", "x.com", "twitter.com", "facebook.com")


def _is_under(host: str, domains: tuple[str, ...]) -> bool:
    """Match whole domain labels: netflix.com is not x.com, nor gov.evil.com a government host."""
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _authority_signals(canonical: str, record: dict[str, Any]) -> dict[str, Any]:
    host = canonical.split("/")[2]
    if _is_under(host, PRIMARY_DOMAINS) or PRIMARY_TLD.search(host):
        tier = "primary"
    elif _is_under(host, COMMUNITY_DOMAINS):
        tier = "community"
    else:
        tier = "secondary"
    return {
        "host": host,
        "tier": tier,
        "has_publisher": bool(record.get("publisher")),
        "has_publication_date": bool(record.get("published_at")),
        "signal_type": "advisory",
        "note": "來源層級只是品質提示，不得單獨用來否決主張；有疑慮時在報告中標註查證建議。",
    }


def register_sources(payload: dict[str, Any]) -> dict[str, Any]:
    """Register sources into an append-only ledger with stable ids and duplicate merging."""
    sources = require(payload, "sources", "source.list-required")
    if not isinstance(sources, list):
        raise SemanticError("source.list-required", "sources must be a list of objects")
    run_dir = resolve_run_dir(payload)
    ledger_path = run_dir / "sources.jsonl"
    existing = {record["canonical_url"]: record for record in read_jsonl(ledger_path)}

    registered: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    redacted_params: list[str] = []
    for index, item in enumerate(sources):
        if not isinstance(item, dict):
            raise SemanticError("source.entry-invalid", "sources[" + str(index) + "] must be an object")
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            raise SemanticError("source.url-required", "sources[" + str(index) + "].url is required")
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise SemanticError(
                "source.title-required",
                "sources[" + str(index) + "].title is required for a citable bibliography",
            )
        canonical = canonical_url(url)
        removed = stripped_credentials(url)
        if removed:
            redacted_params.extend(removed)
        if canonical in existing:
            duplicates.append({"source_id": existing[canonical]["source_id"], "canonical_url": canonical})
            continue
        record = {
            "source_id": "S" + digest(canonical)[:10],
            "url": canonical,
            "credential_params_removed": removed,
            "canonical_url": canonical,
            "title": title.strip(),
            "publisher": item.get("publisher"),
            "published_at": item.get("published_at"),
            "accessed_at": item.get("accessed_at") or now_utc(),
            "source_type": item.get("source_type", "web"),
            "language": item.get("language", "unknown"),
            "authority_signals": _authority_signals(canonical, item),
            "registered_at": now_utc(),
        }
        existing[canonical] = record
        registered.append(record)

    append_jsonl(ledger_path, registered)
    return {
        "status": "OK",
        "ledger_path": str(ledger_path),
        "registered": registered,
        "duplicates": duplicates,
        "redaction_applied": bool(redacted_params),
        "redacted_query_params": sorted(set(redacted_params)),
        "counts": {"registered": len(registered), "duplicates": len(duplicates), "total": len(existing)},
    }
