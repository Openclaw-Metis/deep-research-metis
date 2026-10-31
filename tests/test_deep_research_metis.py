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
sys.path.insert(0, str(SKILL_ROOT / "tests"))

import claim_ledger  # noqa: E402
import evidence_store  # noqa: E402
import report_render  # noqa: E402
import report_verify  # noqa: E402
import research_plan  # noqa: E402
import research_store  # noqa: E402
import run_function  # noqa: E402
import run_manifest  # noqa: E402
import source_ledger  # noqa: E402
import verification_benchmark  # noqa: E402

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


    def test_cjk_and_percent_encoded_paths_share_one_identity(self) -> None:
        self.assertEqual(
            research_store.canonical_url("https://example.org/wiki/資料中心"),
            research_store.canonical_url("https://example.org/wiki/%e8%b3%87%e6%96%99%e4%b8%ad%e5%bf%83"),
        )


class SourceAuthorityTests(unittest.TestCase):
    def tiers(self, *urls: str) -> list[str]:
        with tempfile.TemporaryDirectory() as workspace:
            registered = source_ledger.register_sources(
                {"run_dir": workspace, "sources": [{"url": url, "title": "T"} for url in urls]}
            )
        return [record["authority_signals"]["tier"] for record in registered["registered"]]

    def test_hosts_match_on_whole_domain_labels(self) -> None:
        self.assertEqual(
            self.tiers(
                "https://www.netflix.com/tudum",
                "https://www.fake.gov.evil.com/a",
                "https://www.moea.gov.tw/a",
                "https://x.com/a",
            ),
            ["secondary", "secondary", "primary", "community"],
        )


class CitationParsingTests(unittest.TestCase):
    def test_every_citation_form_expands_to_numbers(self) -> None:
        cases = {"[1]": [1], "[1, 3]": [1, 3], "[2-4]": [2, 3, 4], "[1][2]": [1, 2], "［6］": [6], "【7】": [7], "[1、3-4]": [1, 3, 4]}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(research_store.citation_numbers(text), expected)

    def test_years_in_brackets_and_absurd_ranges_do_not_expand(self) -> None:
        self.assertEqual(research_store.citation_numbers("[2025]"), [])
        self.assertEqual(research_store.citation_numbers("[1-999]"), [1, 999])


class SentenceSplitTests(unittest.TestCase):
    def test_decimals_versions_and_domains_do_not_end_a_sentence(self) -> None:
        for sentence in ("用電量達 3.5 TWh，成長 12.4%。", "arxiv.org hosts version 2.1 of the paper.", "U.S. demand rose, e.g. in Texas."):
            with self.subTest(sentence=sentence):
                self.assertEqual(claim_ledger._split_sentences(sentence), [sentence])

    def test_trailing_citation_stays_with_its_sentence(self) -> None:
        self.assertEqual(claim_ledger._split_sentences("甲成長。[1] 乙下滑 [2]。"), ["甲成長。[1]", "乙下滑 [2]。"])

    def test_short_cited_claim_is_not_discarded(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            result = claim_ledger.extract_claims({"run_dir": workspace, "report_markdown": "## 發現\n\n甲成長 5% [1]。\n"})
        self.assertEqual(result["counts"]["cited"], 1)


class QuantityTests(unittest.TestCase):
    def test_years_and_cross_references_are_not_quantities(self) -> None:
        for text in ("2025 年的政策方向仍未明朗。", "詳見第 3 節與表 2。", "between 2023 and 2025", "See Section 4 and Figure 2."):
            with self.subTest(text=text):
                self.assertEqual(research_store.quantity_values(text), [])

    def test_year_shaped_measurements_stay_quantities(self) -> None:
        self.assertEqual(research_store.quantity_values("裝置容量達 2000 MW"), [2000.0])

    def test_recent_is_not_a_hedge(self) -> None:
        self.assertEqual(research_store.unmatched_quantities("近年成長 12%", ["成長 12.4%"]), [12.0])
        self.assertEqual(research_store.unmatched_quantities("成長近 12%", ["成長 12.4%"]), [])

    def test_thousands_separators_compare_by_value(self) -> None:
        self.assertEqual(research_store.unmatched_quantities("用電 1,280 GWh", ["用電 1280 GWh"]), [])


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

    def test_table_header_is_not_a_claim_and_rows_are(self) -> None:
        report = "## 發現\n\n| 廠商 2025 | 市占 |\n| --- | --- |\n| 甲 | 45% |\n"
        with tempfile.TemporaryDirectory() as workspace:
            result = claim_ledger.extract_claims({"run_dir": workspace, "report_markdown": report, "require_cited_claims": False})
        self.assertEqual([(claim["text"], claim["origin"]) for claim in result["claims"]], [("甲 45%", "table")])

    def test_body_section_with_bibliography_alias_stays_in_scope(self) -> None:
        report = "## 資料來源比較\n\n甲機構低估了 30% 的用電量。\n\n## 參考來源\n\n[1] 報告 https://example.org/a\n"
        titles, lines = research_store.find_bibliography(report)
        self.assertEqual(titles, ["參考來源"])
        self.assertEqual(len(lines), 1)

    def test_grouped_bibliography_with_subheadings_is_recognised(self) -> None:
        report = "## 參考來源\n\n### 官方\n\n[1] 報告 https://example.org/a\n\n### 業界\n\n[2] 報告 https://example.org/b\n"
        self.assertEqual(len(research_store.find_bibliography(report)[1]), 2)

    def test_structure_rejects_a_body_section_posing_as_bibliography(self) -> None:
        result = report_verify.check_structure(
            {"report_markdown": "## 資料來源比較\n\n各機構口徑不同 [1]。\n", "required_sections": ["bibliography"]}
        )
        self.assertTrue(any(item["code"] == "section_missing" for item in result["findings"]))

    def test_citation_check_warns_when_sources_fall_below_the_plan(self) -> None:
        report = "## 發現\n\n甲機構指出成長趨勢明確 [1]。\n\n## 參考來源\n\n[1] 報告 https://example.org/a\n"
        with tempfile.TemporaryDirectory() as workspace:
            research_plan.build_plan({"run_dir": workspace, "question": "Q", "sub_questions": ["a"], "mode": "deep"})
            source_ledger.register_sources({"run_dir": workspace, "sources": [{"url": "https://example.org/a", "title": "A"}]})
            result = report_verify.check_citations({"run_dir": workspace, "report_markdown": report})
        self.assertEqual(result["status"], "PASS")
        finding = next(item for item in result["findings"] if item["code"] == "source_count_below_plan")
        self.assertEqual((finding["resolved_sources"], finding["min_sources"]), (1, 20))

    def test_changed_digit_fails_despite_full_lexical_overlap(self) -> None:
        report = REPORT.replace("成長 18%", "成長 81%")
        with tempfile.TemporaryDirectory() as workspace:
            registered = source_ledger.register_sources(
                {"run_dir": workspace, "sources": [{"url": "https://example.org/report", "title": "年報"}]}
            )
            evidence_store.append_evidence(
                {
                    "run_dir": workspace,
                    "evidence": [
                        {"source_id": registered["registered"][0]["source_id"], "quote": "甲機構指出離岸風電併網容量在 2026 年成長 18%。"}
                    ],
                }
            )
            claim_ledger.extract_claims({"run_dir": workspace, "report_markdown": report})
            report_verify.check_citations({"run_dir": workspace, "report_markdown": report})
            result = report_verify.check_claim_support({"run_dir": workspace})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["claims"][0]["verdict"], "partial")
        self.assertEqual(result["claims"][0]["unmatched_numbers"], [81.0])
        self.assertTrue(any(item["code"] == "claim_number_unmatched" for item in result["findings"]))

    def test_support_verdict_does_not_depend_on_quote_order(self) -> None:
        english = "Quarterly revenue at the unrelated firm stayed essentially flat this year."
        chinese = "這段中文引文談的是完全無關的海洋生態保育議題與志工活動。"
        report = "## 發現\n\n資料中心的需量反應能力仍然有限 [1]。\n\n## 參考來源\n\n[1] 報告 https://example.org/a\n"
        verdicts = []
        for quotes in ((english, chinese), (chinese, english)):
            with tempfile.TemporaryDirectory() as workspace:
                registered = source_ledger.register_sources(
                    {"run_dir": workspace, "sources": [{"url": "https://example.org/a", "title": "A"}]}
                )
                source_id = registered["registered"][0]["source_id"]
                evidence_store.append_evidence(
                    {"run_dir": workspace, "evidence": [{"source_id": source_id, "quote": quote} for quote in quotes]}
                )
                claim_ledger.extract_claims({"run_dir": workspace, "report_markdown": report})
                report_verify.check_citations({"run_dir": workspace, "report_markdown": report})
                verdicts.append(report_verify.check_claim_support({"run_dir": workspace})["claims"][0]["verdict"])
        self.assertEqual(verdicts, ["unsupported", "unsupported"])

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


class RunStateTests(unittest.TestCase):
    def test_manifest_rejects_a_gate_that_contradicts_its_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            Path(workspace, "claim_support.json").write_text('{"status": "FAIL", "report_digest": "sha256:0"}', encoding="utf-8")
            with self.assertRaises(research_store.SemanticError) as caught:
                run_manifest.write_manifest(
                    {"run_dir": workspace, "phase": "verification", "gate_results": [{"gate": "report-verify.check_claim_support", "status": "PASS"}]}
                )
            self.assertEqual(caught.exception.rule_id, "manifest.gate-status-mismatch")

    def test_manifest_rejects_a_pass_with_no_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as workspace, self.assertRaises(research_store.SemanticError):
            run_manifest.write_manifest(
                {"run_dir": workspace, "phase": "verification", "gate_results": [{"gate": "check_structure", "status": "PASS"}]}
            )

    def test_manifest_records_a_true_gate_and_the_verification_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            Path(workspace, "claim_support.json").write_text('{"status": "FAIL", "report_digest": "sha256:0"}', encoding="utf-8")
            run_manifest.write_manifest(
                {"run_dir": workspace, "phase": "verification", "gate_results": [{"gate": "check_claim_support", "status": "FAIL"}]}
            )
            manifest = json.loads(Path(workspace, "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["verification"]["claim_support.json"]["status"], "FAIL")

    def test_plan_refuses_a_second_question_in_one_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            first = {"run_dir": workspace, "question": "問題甲", "sub_questions": ["a"]}
            research_plan.build_plan(first)
            with self.assertRaises(research_store.SemanticError) as caught:
                research_plan.build_plan({**first, "question": "問題乙"})
            self.assertEqual(caught.exception.rule_id, "plan.run-dir-reused")
            replaced = research_plan.build_plan({**first, "question": "問題乙", "replace_plan": True})
            self.assertEqual(replaced["plan"]["question"], "問題乙")

    def test_plan_rerun_keeps_its_creation_time(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            payload = {"run_dir": workspace, "question": "問題", "sub_questions": ["a"]}
            first = research_plan.build_plan(payload)["plan"]
            with mock.patch.object(research_plan, "now_utc", return_value="2099-01-01T00:00:00Z"):
                second = research_plan.build_plan(payload)["plan"]
        self.assertEqual(first["created_at"], second["created_at"])


class RenderTests(unittest.TestCase):
    def test_anchors_live_on_bibliography_entries_only(self) -> None:
        report = "# 題目\n\n- 甲機構的主張內容 [1]。\n\n## 參考來源\n\n[1] 報告一 https://example.org/a\n[2] 報告二 https://example.org/b\n"
        blocks, _ = report_render._render_blocks(report)
        page = "\n".join(blocks)
        self.assertEqual(page.count('id="ref-1"'), 1)
        self.assertEqual(page.count('id="ref-2"'), 1)
        self.assertEqual(page.count('class="ref"'), 2)
        self.assertLess(page.index('href="#ref-1"'), page.index('id="ref-1"'))
        self.assertIn('<a href="https://example.org/a" rel="noreferrer">', page)

    def test_grouped_citation_links_each_number(self) -> None:
        self.assertEqual(report_render._inline("甲 [1, 2]").count('href="#ref-'), 2)

    def test_quotes_cannot_break_out_of_an_autolinked_href(self) -> None:
        rendered = report_render._inline('見 https://example.org/a"onmouseover="alert(1)')
        self.assertIn('href="https://example.org/a"', rendered)
        self.assertNotIn('onmouseover="alert(1)"></a>', rendered)
        self.assertNotIn('<a href="https://example.org/a"onmouseover', rendered)

    def test_markdown_link_with_query_is_not_double_escaped(self) -> None:
        self.assertIn('href="https://example.org/a?x=1&amp;y=2"', report_render._inline("[來源](https://example.org/a?x=1&y=2)"))

    def test_default_footer_follows_the_report_language_and_claims_no_more_than_was_checked(self) -> None:
        self.assertIn("not a semantic review", report_render.DEFAULT_FOOTERS["en"])
        self.assertNotIn("所有主張", report_render.DEFAULT_FOOTERS["zh-TW"])


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

    def test_oversized_result_keeps_its_verdict(self) -> None:
        result = {
            "status": "FAIL",
            "report_path": "claim_support.json",
            "summary": {"unsupported": 900},
            "claims": [{"text": "x" * 200} for _ in range(900)],
            "findings": [{"code": "claim_unsupported"} for _ in range(900)],
        }
        contract = {"result_policy": {"max_inline_bytes": 1024, "overflow_action": "summarize"}}
        summarized, metadata = run_function._apply_result_policy(contract, result)
        self.assertEqual(metadata["overflow_action"], "summarize")
        self.assertEqual(summarized["status"], "FAIL")
        self.assertEqual(summarized["summary"], {"unsupported": 900})
        self.assertEqual(summarized["report_path"], "claim_support.json")
        self.assertEqual(summarized["findings_total"], 900)
        self.assertEqual(len(summarized["findings"]), run_function.MAX_SUMMARY_FINDINGS)
        self.assertEqual(summarized["omitted_keys"], ["claims"])

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


class VerificationBenchmarkTests(unittest.TestCase):
    def test_development_split_agrees_with_every_label(self) -> None:
        data = json.loads(verification_benchmark.BENCHMARK.read_text(encoding="utf-8"))
        cases = [case for case in data["cases"] if case["split"] == "development"]
        report = verification_benchmark.score(SKILL_ROOT, cases)
        self.assertEqual(report["disagreements"], [])


def research_store_digest(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
