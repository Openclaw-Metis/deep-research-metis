"""Evidence persistence function group.

Every factual claim in a report must trace back to a quote captured here. The
store is append-only: quotes are hashed, bound to a registered source id, and
never rewritten, so a later verification pass reads exactly what the run saw.
"""

from __future__ import annotations

from typing import Any

from research_store import (
    SemanticError,
    append_jsonl,
    bilingual_length,
    digest,
    now_utc,
    read_jsonl,
    require,
    resolve_run_dir,
)

MAX_QUOTE_LENGTH = 1200
MIN_QUOTE_LENGTH = 8


def append_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist verbatim quotes against registered sources and reject unusable entries."""
    entries = require(payload, "evidence", "evidence.list-required")
    if not isinstance(entries, list):
        raise SemanticError("evidence.list-required", "evidence must be a list of objects")
    run_dir = resolve_run_dir(payload)
    known_sources = {record["source_id"] for record in read_jsonl(run_dir / "sources.jsonl")}
    if not known_sources:
        raise SemanticError("evidence.sources-not-registered", "register sources before appending evidence")

    evidence_path = run_dir / "evidence.jsonl"
    seen = {record["quote_hash"] for record in read_jsonl(evidence_path)}
    appended: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise SemanticError("evidence.entry-invalid", "evidence[" + str(index) + "] must be an object")
        source_id = item.get("source_id")
        quote = item.get("quote")
        if source_id not in known_sources:
            raise SemanticError(
                "evidence.source-unknown",
                "evidence[" + str(index) + "].source_id is not in the source ledger",
            )
        if not isinstance(quote, str) or len(quote.strip()) < MIN_QUOTE_LENGTH:
            rejected.append({"index": index, "reason": "quote-too-short"})
            continue
        if len(quote) > MAX_QUOTE_LENGTH:
            rejected.append({"index": index, "reason": "quote-too-long"})
            continue
        quote_hash = digest(source_id + "|" + quote.strip())
        if quote_hash in seen:
            rejected.append({"index": index, "reason": "duplicate-quote"})
            continue
        seen.add(quote_hash)
        appended.append(
            {
                "evidence_id": "E" + quote_hash[:10],
                "source_id": source_id,
                "quote": quote.strip(),
                "quote_hash": quote_hash,
                "locator": item.get("locator"),
                "note": item.get("note"),
                "measured_length": bilingual_length(quote),
                "captured_at": item.get("retrieved_at") or now_utc(),
            }
        )

    append_jsonl(evidence_path, appended)
    return {
        "status": "OK",
        "evidence_path": str(evidence_path),
        "appended": appended,
        "rejected": rejected,
        "counts": {"appended": len(appended), "rejected": len(rejected), "total": len(seen)},
    }
