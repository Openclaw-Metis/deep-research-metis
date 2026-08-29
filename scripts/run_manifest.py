"""Run manifest function group.

The manifest is what makes a research run resumable and auditable: it records
which phase completed, which artifacts exist with their content digests, and
which gate results were observed. Phases already recorded as complete are kept,
so a resumed run never silently reruns approved work.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from research_store import SemanticError, now_utc, require, resolve_run_dir, write_json_atomic

KNOWN_PHASES = ("plan", "retrieval", "evidence", "drafting", "verification", "delivery")
TRACKED_ARTIFACTS = (
    "research_plan.json",
    "sources.jsonl",
    "evidence.jsonl",
    "claims.jsonl",
    "citation_map.json",
    "claim_support.json",
)
GATE_STATUSES = ("PASS", "FAIL", "BLOCKED", "SKIPPED")


def _artifact_digests(run_dir) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name in TRACKED_ARTIFACTS:
        path = run_dir / name
        if not path.is_file():
            continue
        records.append(
            {
                "artifact": name,
                "bytes": path.stat().st_size,
                "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return records


def write_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Merge one phase result into the run manifest without discarding earlier phases."""
    run_dir = resolve_run_dir(payload)
    phase = require(payload, "phase", "manifest.phase-required")
    if phase not in KNOWN_PHASES:
        raise SemanticError("manifest.phase-unknown", "phase must be one of: " + ", ".join(KNOWN_PHASES))
    phase_status = payload.get("phase_status", "complete")
    if phase_status not in ("complete", "partial", "blocked"):
        raise SemanticError("manifest.phase-status-invalid", "phase_status must be complete, partial, or blocked")
    gate_results = payload.get("gate_results", [])
    if not isinstance(gate_results, list):
        raise SemanticError("manifest.gate-results-invalid", "gate_results must be a list")
    for gate in gate_results:
        if not isinstance(gate, dict) or gate.get("status") not in GATE_STATUSES:
            raise SemanticError("manifest.gate-status-invalid", "each gate result needs a status of " + "/".join(GATE_STATUSES))

    manifest_path = run_dir / "run_manifest.json"
    manifest: dict[str, Any] = {"schema_version": "1.0.0", "phases": {}, "gate_results": [], "created_at": now_utc()}
    if manifest_path.is_file():
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            manifest.update(loaded)
    manifest.setdefault("phases", {})
    previous = manifest["phases"].get(phase, {})
    if previous.get("status") == "complete" and phase_status != "complete" and not payload.get("allow_downgrade", False):
        raise SemanticError("manifest.phase-downgrade-blocked", "a completed phase is not downgraded without allow_downgrade")

    manifest["run_id"] = manifest.get("run_id") or "RUN-" + hashlib.sha256(str(run_dir).encode("utf-8")).hexdigest()[:10]
    manifest["phases"][phase] = {
        "status": phase_status,
        "updated_at": now_utc(),
        "notes": payload.get("notes"),
    }
    manifest["gate_results"] = [gate for gate in manifest.get("gate_results", []) if gate.get("phase") != phase]
    manifest["gate_results"].extend({**gate, "phase": phase} for gate in gate_results)
    manifest["artifacts"] = _artifact_digests(run_dir)
    manifest["updated_at"] = now_utc()
    write_json_atomic(manifest_path, manifest)
    return {
        "status": "OK",
        "manifest_path": str(manifest_path),
        "run_id": manifest["run_id"],
        "phases": manifest["phases"],
        "artifact_count": len(manifest["artifacts"]),
    }
