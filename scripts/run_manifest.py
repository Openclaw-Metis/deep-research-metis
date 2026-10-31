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
    "structure_check.json",
    "citation_map.json",
    "claim_support.json",
    "report.md",
    "report.html",
)
GATE_STATUSES = ("PASS", "FAIL", "BLOCKED", "SKIPPED")
GATE_ARTIFACTS = {
    "check_structure": "structure_check.json",
    "check_citations": "citation_map.json",
    "check_claim_support": "claim_support.json",
}


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


def _gate_artifact(gate: dict[str, Any]) -> str | None:
    name = str(gate.get("gate", ""))
    return GATE_ARTIFACTS.get(name.rsplit(".", 1)[-1])


def _reject_contradicted_gates(run_dir, gate_results: list[dict[str, Any]]) -> None:
    """Hold verification gates to their artifacts so a manifest cannot overstate a run."""
    for gate in gate_results:
        artifact_name = _gate_artifact(gate)
        if artifact_name is None or gate["status"] not in ("PASS", "FAIL"):
            continue
        artifact_path = run_dir / artifact_name
        observed = None
        if artifact_path.is_file():
            observed = json.loads(artifact_path.read_text(encoding="utf-8")).get("status")
        if observed != gate["status"]:
            raise SemanticError(
                "manifest.gate-status-mismatch",
                str(gate.get("gate")) + " is recorded as " + gate["status"] + " but " + artifact_name + " reports " + str(observed),
            )


def _verification_snapshot(run_dir) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for name in GATE_ARTIFACTS.values():
        path = run_dir / name
        if path.is_file():
            artifact = json.loads(path.read_text(encoding="utf-8"))
            snapshot[name] = {"status": artifact.get("status"), "report_digest": artifact.get("report_digest")}
    return snapshot


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
    _reject_contradicted_gates(run_dir, gate_results)

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
    manifest["verification"] = _verification_snapshot(run_dir)
    manifest["updated_at"] = now_utc()
    write_json_atomic(manifest_path, manifest)
    return {
        "status": "OK",
        "manifest_path": str(manifest_path),
        "run_id": manifest["run_id"],
        "phases": manifest["phases"],
        "artifact_count": len(manifest["artifacts"]),
    }
