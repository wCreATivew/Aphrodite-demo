from __future__ import annotations

from pathlib import Path

from semantic_trigger.clarify import build_clarification_question
from semantic_trigger.config import load_app_config
from semantic_trigger.engine import SemanticTriggerEngine
from semantic_trigger.error_ledger import build_ledger_row
from semantic_trigger.metrics import EvalRow, compute_decision_level_metrics, compute_difficulty_metrics
from semantic_trigger.registry import load_trigger_registry


def _build_engine() -> SemanticTriggerEngine:
    root = Path(__file__).resolve().parents[2]
    reg = load_trigger_registry(str(root / "data" / "triggers" / "default_triggers.yaml"))
    cfg = load_app_config(str(root / "configs" / "app.example.yaml"))
    return SemanticTriggerEngine.build_default(reg, cfg)


def test_clarification_question_for_multi_missing_slots() -> None:
    q = build_clarification_question(["recipient", "content"], selected_trigger="send_message")
    assert isinstance(q, str)
    assert "收件人" in q or "发给谁" in q
    assert "内容" in q


def test_engine_debug_contains_phase2_fields() -> None:
    eng = _build_engine()
    res = eng.infer("message queue tutorial")
    debug = dict(res.debug_trace or {})
    assert "top_k_candidates" in debug
    assert "recall_scores" in debug
    assert "rerank_scores" in debug
    assert "margin" in debug
    assert "config_version" in debug
    assert "policy_version" in debug
    assert "dataset_version" in debug
    assert "timestamp" in debug


def test_build_ledger_row_schema() -> None:
    eng = _build_engine()
    res = eng.infer("set reminder architecture")
    row = build_ledger_row(
        query="set reminder architecture",
        result=res,
        expected_decision="no_trigger",
        expected_trigger="",
    )
    required_keys = {
        "query",
        "predicted_decision",
        "predicted_trigger",
        "expected_decision",
        "expected_trigger",
        "top_k_candidates",
        "recall_scores",
        "rerank_scores",
        "margin",
        "extracted_slots",
        "missing_slots",
        "clarification_question",
        "reasons",
        "config_version",
        "policy_version",
        "dataset_version",
        "timestamp",
        "error_type",
    }
    assert required_keys.issubset(set(row.keys()))


def test_layered_metrics() -> None:
    rows = [
        EvalRow(
            query="q1",
            expected_decision="trigger",
            expected_trigger="set_reminder",
            predicted_decision="trigger",
            predicted_trigger="set_reminder",
            difficulty="easy",
        ),
        EvalRow(
            query="q2",
            expected_decision="trigger",
            expected_trigger="send_message",
            predicted_decision="ask_clarification",
            predicted_trigger="send_message",
            difficulty="hard",
        ),
    ]
    decision = compute_decision_level_metrics(rows)
    difficulty = compute_difficulty_metrics(rows)
    assert "trigger" in decision
    assert "ask_clarification" in decision
    assert "easy" in difficulty
    assert "hard" in difficulty
