"""Regression tests for deep-research-metis.

Standard library only: run with `python -m unittest discover tests` from the
skill root. The tests exercise the function groups directly and the governed
runner as a subprocess, so both the domain logic and the runtime guards stay
covered.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import claim_ledger  # noqa: E402
import evidence_store  # noqa: E402
import report_render  # noqa: E402
import report_verify  # noqa: E402
import research_store  # noqa: E402
import run_function  # noqa: E402
import source_ledger  # noqa: E402

RUNNER = SKILL_ROOT / "scripts" / "run_function.py"

REPORT = """# 研究報告

## Executive Summary 執行摘要

甲機構指出離岸風電併網容量在 2026 年成長 18% [1]。

## Bibliography 參考來源

[1] 甲機構，離岸風電年報，2026。https://example.org/report
"""


def call_runner(tool_id: str, payload: dict) -> tuple[int, dict]:
    process = subprocess.run(
        [sys.executable, "-B", str(RUNNER), tool_id],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    return process.returncode, json.loads(process.stdout)


def prepare_verified_workspace(workspace: str) -> None:
    Path(workspace, "report.md").write_text(REPORT, encoding="utf-8", newline="\n")
    registered = source_ledger.register_sources(
        {"run_dir": workspace, "sources": [{"url": "https://example.org/report", "title": "年報"}]}
    )
    source_id = registered["registered"][0]["source_id"]
    evidence_store.append_evidence(
        {
            "run_dir": workspace,
            "evidence": [{"source_id": source_id, "quote": "甲機構指出離岸風電併網容量在 2026 年成長 18%。"}],
        }
    )
    payload = {"run_dir": workspace, "report_path": "report.md"}
    claim_ledger.extract_claims(payload)
    structure = report_verify.check_structure(
        {**payload, "required_sections": ["executive-summary", "bibliography"]}
    )
    citations = report_verify.check_citations(payload)
    support = report_verify.check_claim_support({"run_dir": workspace})
    if {structure["status"], citations["status"], support["status"]} != {"PASS"}:
        raise AssertionError("verification fixture failed")


def approval_for(report: str, *, target: str = "report.html", expires_delta: int = 1) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "decision": "granted",
        "granted_by": "test-reviewer",
        "granted_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(days=expires_delta)).isoformat(),
        "scope": "write-report-deliverable",
        "target": target,
        "subject_digest": "sha256:" + research_store.digest(report),
    }


class CanonicalUrlTests(unittest.TestCase):
    def test_tracking_and_www_are_normalised(self) -> None:
        first = research_store.canonical_url("https://www.example.org/a/?utm_source=news")
        second = research_store.canonical_url("https://example.org/a")
        self.assertEqual(first, second)

    def test_credential_parameters_are_stripped(self) -> None:
        url = "https://api.example.org/v1?api_key=secretvalue&topic=grid"
        self.assertNotIn("secretvalue", research_store.canonical_url(url))
        self.assertEqual(research_store.stripped_credentials(url), ["api_key"])

    def test_relative_url_is_rejected(self) -> None:
        with self.assertRaises(research_store.SemanticError):
            research_store.canonical_url("/reports/2026")

    def test_non_http_and_userinfo_urls_are_rejected(self) -> None:
        for url in ("ftp://example.org/report", "https://user:password@example.org/report"):
            with self.subTest(url=url), self.assertRaises(research_store.SemanticError):
                research_store.canonical_url(url)


class BilingualMeasureTests(unittest.TestCase):
    def test_length_counts_cjk_characters_and_latin_words(self) -> None:
        self.assertEqual(research_store.bilingual_length("資料中心 grid load"), 6)

    def test_citation_marks_do_not_become_anchors(self) -> None:
        self.assertEqual(research_store.anchor_tokens("成長速度快於建置速度 [2]"), set())

    def test_same_script_scoring_rewards_real_overlap(self) -> None:
        score, method = research_store.support_score(
            "資料中心用電量自 2025 年起持續攀升。",
            "資料中心用電量自 2025 年起持續攀升，主要壓力來自訓練負載。",
        )
        self.assertEqual(method, "same-script-lexical")
        self.assertGreater(score, 0.45)

    def test_cross_script_scoring_uses_anchors(self) -> None:
        score, method = research_store.support_score(
            "國際機構指出該比例在 2026 年達到 3%。",
            "The share could reach 3% of global demand in 2026.",
        )
        self.assertEqual(method, "cross-script-anchor")
        self.assertGreaterEqual(score, 0.6)

    def test_cross_script_without_anchor_is_unverifiable(self) -> None:
        score, method = research_store.support_score(
            "兩份來源都指向同一個結論。",
            "Both sources point to the same conclusion about grid flexibility.",
        )
        self.assertEqual(method, "insufficient-signal")
        self.assertEqual(score, 0.0)


class WorkspaceBoundaryTests(unittest.TestCase):
    def test_run_dir_inside_the_skill_is_rejected(self) -> None:
        with self.assertRaises(research_store.SemanticError) as caught:
            research_store.resolve_run_dir({"run_dir": str(SKILL_ROOT / "scratch")})
        self.assertEqual(caught.exception.rule_id, "workspace.outside-skill-root")

    def test_path_escaping_the_workspace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            with self.assertRaises(research_store.SemanticError):
                research_store.resolve_inside(Path(workspace), "../escape.md", "test.escape")


class LedgerTests(unittest.TestCase):
    def test_evidence_requires_a_registered_source(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            source_ledger.register_sources(
                {"run_dir": workspace, "sources": [{"url": "https://example.org/report", "title": "年報"}]}
            )
            with self.assertRaises(research_store.SemanticError) as caught:
                evidence_store.append_evidence(
                    {"run_dir": workspace, "evidence": [{"source_id": "Sdeadbeef00", "quote": "一段夠長的引文內容。"}]}
                )
            self.assertEqual(caught.exception.rule_id, "evidence.source-unknown")

    def test_duplicate_sources_merge_into_one_identity(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            payload = {"run_dir": workspace, "sources": [{"url": "https://example.org/a", "title": "A"}]}
            source_ledger.register_sources(payload)
            second = source_ledger.register_sources(
                {"run_dir": workspace, "sources": [{"url": "https://www.example.org/a/", "title": "A"}]}
            )
            self.assertEqual(second["counts"]["registered"], 0)
            self.assertEqual(second["counts"]["duplicates"], 1)


class VerificationTests(unittest.TestCase):
    def test_bibliography_sentences_are_not_claims(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            result = claim_ledger.extract_claims({"run_dir": workspace, "report_markdown": REPORT})
            sections = {claim["section"] for claim in result["claims"]}
            self.assertNotIn("bibliography", sections)
            self.assertEqual(result["counts"]["cited"], 1)

    def test_structure_accepts_bilingual_headings(self) -> None:
        result = report_verify.check_structure(
            {"report_markdown": REPORT, "required_sections": ["executive-summary", "bibliography"]}
        )
        self.assertEqual(result["status"], "PASS")

    def test_structure_reports_placeholder_lines(self) -> None:
        result = report_verify.check_structure(
            {"report_markdown": REPORT + "\n待補：補上限制章節。\n", "required_sections": ["executive-summary"]}
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(item["code"] == "placeholder_present" for item in result["findings"]))

    def test_bibliography_numbers_are_not_inline_citations(self) -> None:
        report = """# 研究報告

## Bibliography 參考來源

[1] 甲機構，離岸風電年報。https://example.org/report
"""
        structure = report_verify.check_structure(
            {"report_markdown": report, "required_sections": ["bibliography"]}
        )
        self.assertEqual(structure["status"], "FAIL")
        self.assertTrue(any(item["code"] == "no_inline_citation" for item in structure["findings"]))

        with tempfile.TemporaryDirectory() as workspace:
            source_ledger.register_sources(
                {"run_dir": workspace, "sources": [{"url": "https://example.org/report", "title": "年報"}]}
            )
            citations = report_verify.check_citations({"run_dir": workspace, "report_markdown": report})
            self.assertEqual(citations["counts"]["inline_citations"], 0)
            self.assertTrue(any(item["code"] == "entry_without_citation" for item in citations["findings"]))

    def test_claim_extraction_replaces_stale_snapshot_on_resume(self) -> None:
        updated_report = REPORT.replace("成長 18%", "成長 22%")
        with tempfile.TemporaryDirectory() as workspace:
            first = claim_ledger.extract_claims({"run_dir": workspace, "report_markdown": REPORT})
            second = claim_ledger.extract_claims({"run_dir": workspace, "report_markdown": updated_report})
            persisted = research_store.read_jsonl(Path(workspace) / "claims.jsonl")
            self.assertEqual(first["counts"]["cited"], 1)
            self.assertEqual(second["counts"]["cited"], 1)
            self.assertEqual(len(persisted), 1)
            self.assertIn("22%", persisted[0]["text"])
            self.assertNotIn("18%", persisted[0]["text"])

    def test_claim_support_rejects_mismatched_report_digests(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            registered = source_ledger.register_sources(
                {"run_dir": workspace, "sources": [{"url": "https://example.org/report", "title": "年報"}]}
            )
            source_id = registered["registered"][0]["source_id"]
            evidence_store.append_evidence(
                {
                    "run_dir": workspace,
                    "evidence": [{"source_id": source_id, "quote": "離岸風電併網容量在 2026 年成長 18%。"}],
                }
            )
            claim_ledger.extract_claims({"run_dir": workspace, "report_markdown": REPORT})
            report_verify.check_citations(
                {"run_dir": workspace, "report_markdown": REPORT.replace("成長 18%", "成長 22%")}
            )
            with self.assertRaises(research_store.SemanticError) as caught:
                report_verify.check_claim_support({"run_dir": workspace})
            self.assertEqual(caught.exception.rule_id, "support.report-digest-mismatch")


class RunnerGuardTests(unittest.TestCase):
    def test_unlisted_function_is_blocked(self) -> None:
        code, envelope = call_runner("report-verify.check_everything", {"run_dir": "."})
        self.assertEqual(code, 3)
        self.assertEqual(envelope["error"]["code"], "unlisted_function")

    def test_invalid_enum_is_blocked_before_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            code, envelope = call_runner(
                "research-plan.build_plan",
                {"run_dir": workspace, "question": "問題", "sub_questions": ["子問題"], "mode": "turbo"},
            )
        self.assertEqual(code, 3)
        self.assertEqual(envelope["error"]["code"], "invalid_arguments")

    def test_write_effect_requires_an_approval_record(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            Path(workspace, "report.md").write_text(REPORT, encoding="utf-8", newline="\n")
            code, envelope = call_runner(
                "report-render.render_html",
                {"run_dir": workspace, "title": "報告", "report_path": "report.md"},
            )
            self.assertEqual(code, 3)
            self.assertEqual(envelope["error"]["code"], "approval_denied")
            self.assertFalse(Path(workspace, "report.html").exists())

    def test_render_requires_current_verification_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            Path(workspace, "report.md").write_text(REPORT, encoding="utf-8", newline="\n")
            with self.assertRaises(research_store.SemanticError) as caught:
                report_render.render_html({"run_dir": workspace, "title": "報告", "report_path": "report.md"})
            self.assertEqual(caught.exception.rule_id, "render.verification-missing")

    def test_approval_must_match_scope_target_subject_and_expiry(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            prepare_verified_workspace(workspace)
            cases = {
                "target": {**approval_for(REPORT), "target": "other.html"},
                "scope": {**approval_for(REPORT), "scope": "different-scope"},
                "subject": {**approval_for(REPORT), "subject_digest": "sha256:" + "0" * 64},
                "expiry": approval_for(REPORT, expires_delta=-1),
            }
            for name, approval in cases.items():
                with self.subTest(name=name):
                    code, envelope = call_runner(
                        "report-render.render_html",
                        {
                            "run_dir": workspace,
                            "title": "報告",
                            "report_path": "report.md",
                            "output_path": "report.html",
                            "_approval": approval,
                        },
                    )
                    self.assertEqual(code, 3)
                    self.assertEqual(envelope["error"]["code"], "approval_denied")
                    self.assertFalse(Path(workspace, "report.html").exists())

    def test_verified_report_with_bound_approval_renders(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            prepare_verified_workspace(workspace)
            code, envelope = call_runner(
                "report-render.render_html",
                {
                    "run_dir": workspace,
                    "title": "報告",
                    "report_path": "report.md",
                    "output_path": "report.html",
                    "_approval": approval_for(REPORT),
                },
            )
            self.assertEqual(code, 0, envelope)
            self.assertEqual(envelope["status"], "OK")
            self.assertTrue(Path(workspace, "report.html").is_file())

    def test_semantic_failure_reports_the_failed_rule(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            code, envelope = call_runner(
                "evidence-store.append_evidence",
                {"run_dir": workspace, "evidence": [{"source_id": "S0000000000", "quote": "一段夠長的引文內容。"}]},
            )
        self.assertEqual(code, 3)
        self.assertEqual(envelope["error"]["failed_rule_id"], "evidence.sources-not-registered")

    def test_registry_digests_match_the_files_on_disk(self) -> None:
        registry = json.loads((SKILL_ROOT / "tools" / "registry.json").read_text(encoding="utf-8"))
        for entry in registry["tools"]:
            contract_path = SKILL_ROOT / entry["contract_ref"]
            runtime_path = SKILL_ROOT / entry["runtime_ref"]
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            module_path = SKILL_ROOT / runtime["module"]
            self.assertEqual(entry["contract_digest"], research_store_digest(contract_path), entry["id"])
            self.assertEqual(entry["runtime_digest"], research_store_digest(runtime_path), entry["id"])
            self.assertEqual(entry["code_digest"], research_store_digest(module_path), entry["id"])
            for dependency in runtime["dependencies"]["bundled_paths"]:
                self.assertEqual(
                    dependency["digest"],
                    research_store_digest(SKILL_ROOT / dependency["path"]),
                    entry["id"] + ":" + dependency["path"],
                )

    def test_runner_blocks_a_stale_bundled_dependency(self) -> None:
        real_digest = run_function._digest

        def fake_digest(path: Path) -> str:
            if path.name == "research_store.py":
                return "sha256:" + "0" * 64
            return real_digest(path)

        with tempfile.TemporaryDirectory() as workspace, mock.patch.object(run_function, "_digest", fake_digest):
            with self.assertRaises(run_function.GuardError) as caught:
                run_function.invoke(
                    "research-plan.build_plan",
                    {"run_dir": workspace, "question": "問題", "sub_questions": ["子問題"]},
                )
        self.assertEqual(caught.exception.code, "dependency_digest_mismatch")


def research_store_digest(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
