"""Research planning function group.

The agent supplies the question and its own sub-questions; this group fixes the
deterministic parts of a run: identifiers, retrieval budget per mode, the
required report sections for the target language, and the stop conditions that
later phases are validated against.
"""

from __future__ import annotations

import json
from typing import Any

from research_store import SemanticError, digest, now_utc, require, resolve_run_dir, write_json_atomic

MODE_BUDGETS = {
    "quick": {"min_sources": 5, "max_sources": 12, "max_queries": 8, "max_sub_questions": 3},
    "standard": {"min_sources": 10, "max_sources": 25, "max_queries": 18, "max_sub_questions": 5},
    "deep": {"min_sources": 20, "max_sources": 45, "max_queries": 35, "max_sub_questions": 8},
    "ultradeep": {"min_sources": 35, "max_sources": 80, "max_queries": 60, "max_sub_questions": 12},
}
REQUIRED_SECTIONS = (
    "executive-summary",
    "introduction",
    "findings",
    "analysis",
    "limitations",
    "methodology",
    "bibliography",
)
SECTION_TITLES = {
    "zh-TW": {
        "executive-summary": "Executive Summary 執行摘要",
        "introduction": "Introduction 研究背景與問題",
        "findings": "Findings 主要發現",
        "analysis": "Analysis 交叉比對與判讀",
        "limitations": "Limitations 限制與注意事項",
        "methodology": "Methodology 方法與檢索紀錄",
        "bibliography": "Bibliography 參考來源",
    },
    "en": {
        "executive-summary": "Executive Summary",
        "introduction": "Introduction",
        "findings": "Findings",
        "analysis": "Analysis",
        "limitations": "Limitations",
        "methodology": "Methodology",
        "bibliography": "Bibliography",
    },
}


def build_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """Turn a question plus caller-authored sub-questions into a versioned run plan."""
    question = require(payload, "question", "plan.question-required")
    sub_questions = require(payload, "sub_questions", "plan.sub-questions-required")
    mode = payload.get("mode", "standard")
    language = payload.get("language", "zh-TW")
    if mode not in MODE_BUDGETS:
        raise SemanticError("plan.mode-unknown", "mode must be quick, standard, deep, or ultradeep")
    if language not in SECTION_TITLES:
        raise SemanticError("plan.language-unsupported", "language must be zh-TW or en")
    if not isinstance(sub_questions, list) or not all(isinstance(item, str) and item.strip() for item in sub_questions):
        raise SemanticError("plan.sub-questions-required", "sub_questions must be a list of non-empty strings")
    budget = MODE_BUDGETS[mode]
    if len(sub_questions) > budget["max_sub_questions"]:
        raise SemanticError(
            "plan.sub-questions-over-budget",
            "mode " + mode + " allows at most " + str(budget["max_sub_questions"]) + " sub-questions",
        )

    run_dir = resolve_run_dir(payload)
    plan_id = "RP-" + digest(question + "|" + mode + "|" + language)[:12]
    plan_path = run_dir / "research_plan.json"
    created_at = now_utc()
    if plan_path.is_file():
        existing = json.loads(plan_path.read_text(encoding="utf-8"))
        # The ledgers in this workspace belong to the existing question; a second
        # question here would cite them as if they had been gathered for it.
        if existing.get("plan_id") != plan_id and not payload.get("replace_plan", False):
            raise SemanticError(
                "plan.run-dir-reused",
                "run_dir already holds a different research plan; use a new run_dir or pass replace_plan=true",
            )
        if existing.get("plan_id") == plan_id:
            created_at = existing.get("created_at", created_at)
    plan = {
        "plan_id": plan_id,
        "created_at": created_at,
        "question": question,
        "mode": mode,
        "language": language,
        "audience": payload.get("audience", "technical-decision-maker"),
        "retrieval_budget": dict(budget),
        "sub_questions": [
            {"id": "SQ%02d" % index, "text": text.strip(), "priority": "primary" if index <= 2 else "secondary"}
            for index, text in enumerate(sub_questions, start=1)
        ],
        "required_sections": [
            {"key": key, "title": SECTION_TITLES[language][key]} for key in REQUIRED_SECTIONS
        ],
        "stop_conditions": [
            "可追溯來源少於 min_sources 時停止並回報證據不足",
            "任一主張缺少已持久化的證據引文時停止並補證",
            "檢索次數達到 max_queries 仍無法覆蓋 primary 子問題時改為部分交付",
        ],
    }
    write_json_atomic(plan_path, plan)
    return {"status": "OK", "plan": plan, "plan_path": str(plan_path)}
