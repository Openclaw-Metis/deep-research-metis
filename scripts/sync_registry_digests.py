#!/usr/bin/env python3
"""Synchronize Code as Tool contract, runtime, code, and dependency digests.

This maintenance command is intentionally deterministic and standard-library
only. It updates runtime metadata first, then binds the resulting metadata in
the closed-world registry so shared helper or asset changes cannot bypass the
runtime integrity guard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_ROOT / "tools" / "registry.json"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temp_path, path)


def declared_dependencies(module_path: Path) -> list[str]:
    source = module_path.read_text(encoding="utf-8")
    dependencies: list[str] = []
    if "from research_store import" in source:
        dependencies.append("scripts/research_store.py")
    if "load_lexicon" in source or "find_bibliography" in source:
        dependencies.append("assets/lexicon/section_aliases.json")
    if not dependencies:
        raise ValueError("runtime module has no declared bundled dependency: " + str(module_path))
    return dependencies


def synchronize(registry_version: str) -> dict[str, Any]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["registry_version"] = registry_version
    for entry in registry["tools"]:
        contract_path = SKILL_ROOT / entry["contract_ref"]
        runtime_path = SKILL_ROOT / entry["runtime_ref"]
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        module_path = SKILL_ROOT / runtime["module"]

        entry["version"] = contract["version"]
        entry["contract_digest"] = file_digest(contract_path)
        entry["code_digest"] = file_digest(module_path)
        runtime["compatible_contract_digest"] = entry["contract_digest"]
        runtime["dependencies"]["bundled_paths"] = [
            {"path": relative, "digest": file_digest(SKILL_ROOT / relative)}
            for relative in declared_dependencies(module_path)
        ]
        write_json_atomic(runtime_path, runtime)
        entry["runtime_digest"] = file_digest(runtime_path)

    write_json_atomic(REGISTRY_PATH, registry)
    return {"registry_version": registry_version, "tools_updated": len(registry["tools"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-version", required=True)
    args = parser.parse_args()
    print(json.dumps(synchronize(args.registry_version), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
