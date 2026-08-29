#!/usr/bin/env python3
"""Governed entrypoint: resolve one allowlisted function ID and invoke it with JSON stdin/stdout.

The runner is the only way a function in this skill is executed. It re-checks
the registry digests, validates the caller payload against the function
contract, enforces the declared effects and approval policy, applies the result
policy, and reports a typed envelope on stdout. Exit code 0 means the function
completed, 2 means it failed, and 3 means a guard blocked it before or after
invocation.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
SECRET_KEY_HINTS = ("api_key", "apikey", "token", "secret", "password", "credential", "access_key")
STATUS_EXIT = {"OK": 0, "FAILED": 2, "BLOCKED": 3}
JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


class GuardError(Exception):
    """Raised when a runtime guard blocks the call before or after invocation."""

    def __init__(self, code: str, message: str, rule_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.rule_id = rule_id


def _inside(root: Path, value: str, prefix: str) -> Path:
    if not isinstance(value, str) or not value.startswith(prefix):
        raise GuardError("path_prefix_invalid", "path must start with " + prefix)
    candidate = (root / value).resolve()
    candidate.relative_to(root)
    return candidate


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_schema(payload: Any, schema: dict[str, Any], location: str = "payload") -> None:
    """Validate the subset of JSON Schema the function contracts actually use."""
    expected = schema.get("type")
    if expected:
        python_type = JSON_TYPES.get(expected)
        if python_type and not isinstance(payload, python_type):
            raise GuardError("invalid_arguments", location + " must be of type " + expected)
        if expected == "integer" and isinstance(payload, bool):
            raise GuardError("invalid_arguments", location + " must be of type integer")
    if "enum" in schema and payload not in schema["enum"]:
        raise GuardError("invalid_arguments", location + " must be one of: " + ", ".join(str(item) for item in schema["enum"]))
    if isinstance(payload, dict):
        for key in schema.get("required", []):
            if key not in payload:
                raise GuardError("invalid_arguments", location + "." + key + " is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(payload) - set(properties) - {"_approval"})
            if unknown:
                raise GuardError("invalid_arguments", location + " has unknown fields: " + ", ".join(unknown))
        for key, sub_schema in properties.items():
            if key in payload and payload[key] is not None:
                _validate_schema(payload[key], sub_schema, location + "." + key)
    if isinstance(payload, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(payload):
            _validate_schema(item, schema["items"], location + "[" + str(index) + "]")


def _enforce_approval(contract: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    effects = contract.get("effects", {})
    policy = contract.get("approval_policy", {})
    if not effects.get("requires_approval") and policy.get("mode") != "required":
        return None
    approval = payload.get("_approval")
    if not isinstance(approval, dict):
        raise GuardError("approval_denied", "this function requires an approval record in payload._approval")
    if approval.get("decision") != "granted":
        raise GuardError("approval_denied", "approval decision is not granted")
    for field in ("granted_by", "granted_at", "scope"):
        if not approval.get(field):
            raise GuardError("approval_denied", "approval record is missing " + field)
    if policy.get("bind_to_target") and not approval.get("target"):
        raise GuardError("approval_denied", "approval must bind to the target artifact")
    return approval


def _redact(value: Any) -> tuple[Any, bool]:
    redacted = False
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if any(hint in str(key).lower() for hint in SECRET_KEY_HINTS):
                cleaned[key] = "[redacted]"
                redacted = True
                continue
            cleaned[key], hit = _redact(item)
            redacted = redacted or hit
        return cleaned, redacted
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            cleaned_item, hit = _redact(item)
            redacted = redacted or hit
            cleaned_list.append(cleaned_item)
        return cleaned_list, redacted
    return value, redacted


def _apply_result_policy(contract: dict[str, Any], result: Any) -> tuple[Any, dict[str, Any]]:
    policy = contract.get("result_policy", {})
    if policy.get("validate_output_schema"):
        output_schema = contract.get("output", {})
        if isinstance(output_schema, dict) and output_schema.get("type"):
            _validate_schema(result, {"type": output_schema["type"]}, "result")
    result, redaction_applied = _redact(result)
    serialized = json.dumps(result, ensure_ascii=False)
    max_inline = int(policy.get("max_inline_bytes", 65536))
    metadata = {"redaction_applied": redaction_applied, "inline_bytes": len(serialized.encode("utf-8")), "overflow_action": None}
    if metadata["inline_bytes"] > max_inline:
        action = policy.get("overflow_action", "summarize")
        metadata["overflow_action"] = action
        if action == "block":
            raise GuardError("result_policy_violation", "result exceeds the inline budget")
        if action == "truncate":
            result = {"truncated": True, "preview": serialized[:max_inline]}
        else:
            result = {"summarized": True, "keys": sorted(result)[:40] if isinstance(result, dict) else [], "inline_bytes": metadata["inline_bytes"]}
    return result, metadata


def _load_module(runtime: dict[str, Any], module_path: Path):
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    spec = importlib.util.spec_from_file_location("code_tool_" + runtime["function_group"].replace("-", "_"), module_path)
    if spec is None or spec.loader is None:
        raise GuardError("entrypoint_unresolved", "cannot load the function group module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run the full guard sequence for one function ID and return the result envelope."""
    events: list[str] = ["scope-check"]
    registry = json.loads((SKILL_ROOT / "tools" / "registry.json").read_text(encoding="utf-8"))
    entry = next((item for item in registry["tools"] if item["id"] == tool_id and item.get("status") == "active"), None)
    if entry is None:
        raise GuardError("unlisted_function", "function ID is not an active registry entry: " + str(tool_id))
    events.append("select")

    contract_path = _inside(SKILL_ROOT, entry["contract_ref"], "tools/contracts/")
    contract_digest = _digest(contract_path)
    if contract_digest != entry["contract_digest"]:
        raise GuardError("contract_digest_mismatch", "function contract digest is stale")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    events.append("load-contract")

    _validate_schema(payload, contract["input_schema"])
    events.append("validate-input")
    approval = _enforce_approval(contract, payload)
    events.append("approval")

    runtime_path = _inside(SKILL_ROOT, entry["runtime_ref"], "tools/runtime/")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    if runtime.get("compatible_contract_digest") != contract_digest:
        raise GuardError("runtime_incompatible", "runtime metadata is incompatible with the function contract")
    module_path = _inside(SKILL_ROOT, runtime["module"], "scripts/")
    if _digest(module_path) != entry["code_digest"]:
        raise GuardError("code_digest_mismatch", "function code digest is stale")
    events.append("resolve-entrypoint")

    allowed_environment = set(runtime["environment"]["allowlist"])
    for key in list(os.environ):
        if key not in allowed_environment:
            del os.environ[key]
    for asset_path in runtime["dependencies"].get("asset_paths", []):
        sys.path.insert(0, str(_inside(SKILL_ROOT, asset_path, "assets/")))
        events.append("resolve-assets")

    module = _load_module(runtime, module_path)
    function = getattr(module, runtime["callable"], None)
    if function is None:
        raise GuardError("entrypoint_unresolved", "declared callable is missing from the module")
    semantic_error = getattr(module, "SemanticError", None)
    events.append("invoke-python")
    try:
        result = function({key: value for key, value in payload.items() if key != "_approval"})
    except Exception as exc:  # noqa: BLE001 - surfaced as a typed envelope below
        if semantic_error is not None and isinstance(exc, semantic_error):
            raise GuardError("semantic_validation_failed", exc.message, rule_id=exc.rule_id) from exc
        raise

    result, metadata = _apply_result_policy(contract, result)
    events.append("validate-output")
    if isinstance(result, dict) and result.get("redaction_applied"):
        metadata["redaction_applied"] = True
    if metadata["redaction_applied"]:
        events.append("redact")
    events.append("result")
    return {
        "status": "OK",
        "tool_id": tool_id,
        "contract_version": contract["version"],
        "contract_digest": contract_digest,
        "code_digest": entry["code_digest"],
        "approval": {"decision": approval["decision"], "scope": approval["scope"]} if approval else None,
        "events": events,
        "redaction_applied": metadata["redaction_applied"],
        "overflow_action": metadata["overflow_action"],
        "result": result,
    }


def main() -> int:
    if len(sys.argv) != 2:
        json.dump({"status": "BLOCKED", "error": {"code": "usage", "message": "usage: run_function.py <group.function>"}}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return STATUS_EXIT["BLOCKED"]
    tool_id = sys.argv[1]
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        json.dump({"status": "BLOCKED", "tool_id": tool_id, "error": {"code": "invalid_arguments", "message": str(exc)}}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return STATUS_EXIT["BLOCKED"]
    try:
        envelope = invoke(tool_id, payload if isinstance(payload, dict) else {})
        status = "OK"
    except GuardError as exc:
        envelope = {"status": "BLOCKED", "tool_id": tool_id, "error": {"code": exc.code, "message": exc.message, "failed_rule_id": exc.rule_id}}
        status = "BLOCKED"
        print(exc.code + ": " + exc.message, file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - the function itself failed
        envelope = {"status": "FAILED", "tool_id": tool_id, "error": {"code": "function_failed", "message": str(exc)}}
        status = "FAILED"
        print("function_failed: " + str(exc), file=sys.stderr)
    json.dump(envelope, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return STATUS_EXIT[status]


if __name__ == "__main__":
    raise SystemExit(main())
