#!/usr/bin/env python3
"""Replay the frozen verification benchmark through the governed runner.

The benchmark data ships with the skill, while the scorer can point at any other
checkout with --skill-root, so an old release and a candidate are measured on
exactly the same cases. Scores are deterministic: no model or network is used.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = SKILL_ROOT / "assets" / "evals" / "verification-benchmark.json"
GATES = {
    "structure": "report-verify.check_structure",
    "citations": "report-verify.check_citations",
    "support": "report-verify.check_claim_support",
}


def call_runner(skill_root: Path, tool_id: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    process = subprocess.run(
        [sys.executable, "-B", str(skill_root / "scripts" / "run_function.py"), tool_id],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        timeout=60,
        shell=False,
    )
    return process.returncode, json.loads(process.stdout.decode("utf-8"))


def gate_status(code: int, envelope: dict[str, Any]) -> str:
    """A guard block or function failure is never a pass, whatever the reason."""
    if code != 0:
        return "BLOCKED"
    return str(envelope["result"].get("status", "BLOCKED"))


def replay_case(skill_root: Path, case: dict[str, Any], run_dir: str) -> dict[str, str]:
    code, envelope = call_runner(skill_root, "source-ledger.register_sources", {"run_dir": run_dir, "sources": case["sources"]})
    if code != 0:
        raise RuntimeError(case["id"] + ": source registration failed: " + json.dumps(envelope, ensure_ascii=False))
    source_ids = [record["source_id"] for record in envelope["result"]["registered"]]
    evidence = [{"source_id": source_ids[item["source"]], "quote": item["quote"]} for item in case["evidence"]]
    code, envelope = call_runner(skill_root, "evidence-store.append_evidence", {"run_dir": run_dir, "evidence": evidence})
    if code != 0:
        raise RuntimeError(case["id"] + ": evidence append failed: " + json.dumps(envelope, ensure_ascii=False))

    Path(run_dir, "report.md").write_text(case["report"], encoding="utf-8", newline="\n")
    report = {"run_dir": run_dir, "report_path": "report.md"}
    call_runner(skill_root, "claim-ledger.extract_claims", {**report, "require_cited_claims": False})
    observed = {
        "structure": gate_status(*call_runner(skill_root, GATES["structure"], {**report, "required_sections": case["required_sections"]})),
        "citations": gate_status(*call_runner(skill_root, GATES["citations"], report)),
        "support": gate_status(*call_runner(skill_root, GATES["support"], {"run_dir": run_dir})),
    }
    return observed


def score(skill_root: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="drm-benchmark-") as run_dir:
            observed = replay_case(skill_root, case, run_dir)
        expected = case["expected"]
        # Only PASS versus not-PASS is labelled: a blocked gate and a failed gate
        # both stop delivery, which is the decision the benchmark measures.
        mismatched = sorted(
            gate for gate, status in expected.items() if (observed[gate] == "PASS") != (status == "PASS")
        )
        should_block = any(status != "PASS" for status in expected.values())
        delivered = all(observed[gate] == "PASS" for gate in expected)
        results.append(
            {
                "id": case["id"],
                "split": case["split"],
                "language": case["language"],
                "expected": expected,
                "observed": observed,
                "agrees": not mismatched,
                "mismatched_gates": mismatched,
                "false_pass": should_block and delivered,
                "false_fail": not should_block and not delivered,
                "should_block": should_block,
            }
        )
    total = len(results)
    blocking = [item for item in results if item["should_block"]]
    return {
        "skill_root": str(skill_root),
        "cases": total,
        "pass_rate": round(sum(item["agrees"] for item in results) / total, 4) if total else 0.0,
        "safety_cases": len(blocking),
        "safety_pass_rate": round(sum(not item["false_pass"] for item in blocking) / len(blocking), 4) if blocking else 1.0,
        "false_pass": [item["id"] for item in results if item["false_pass"]],
        "false_fail": [item["id"] for item in results if item["false_fail"]],
        "disagreements": [item for item in results if not item["agrees"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", default=str(SKILL_ROOT), help="checkout to measure; defaults to this skill")
    parser.add_argument("--split", choices=("development", "held_out", "all"), default="development")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    cases = [case for case in data["cases"] if args.split == "all" or case["split"] == args.split]
    report = score(Path(args.skill_root).resolve(), cases)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "pass_rate={pass_rate} safety_pass_rate={safety_pass_rate} cases={cases} "
            "false_pass={fp} false_fail={ff}".format(
                fp=len(report["false_pass"]), ff=len(report["false_fail"]), **report
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
