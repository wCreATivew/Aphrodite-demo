from __future__ import annotations

from pathlib import Path

from semantic_trigger.config import load_app_config
from semantic_trigger.engine import SemanticTriggerEngine
from semantic_trigger.schemas import EngineResult
from semantic_trigger.registry import load_trigger_registry


def _build_engine() -> SemanticTriggerEngine:
    root = Path(__file__).resolve().parents[2]
    reg = load_trigger_registry(str(root / "data" / "triggers" / "default_triggers.yaml"))
    cfg = load_app_config(str(root / "configs" / "app.example.yaml"))
    return SemanticTriggerEngine.build_default(reg, cfg)


def test_engine_result_contract_fields() -> None:
    eng = _build_engine()
    res = eng.infer("提醒我明天下午开会")

    assert isinstance(res, EngineResult)
    assert hasattr(res, "user_query")
    assert hasattr(res, "decision")
    assert hasattr(res, "selected_trigger")
    assert hasattr(res, "confidence")
    assert hasattr(res, "candidates")
    assert hasattr(res, "extracted_slots")
    assert hasattr(res, "missing_slots")
    assert hasattr(res, "clarification_question")
    assert hasattr(res, "reasons")
    assert hasattr(res, "debug")


def test_candidate_score_contract_and_compat_aliases() -> None:
    eng = _build_engine()
    res = eng.infer("明天下午三点提醒我开会")
    assert res.candidates

    c0 = res.candidates[0]
    assert hasattr(c0, "trigger_id")
    assert hasattr(c0, "recall_score")
    assert hasattr(c0, "rerank_score")
    assert hasattr(c0, "final_score")
    assert hasattr(c0, "notes")

    # backward compatibility for existing modules
    assert c0.combined_score == c0.final_score
    assert res.debug_trace == res.debug
