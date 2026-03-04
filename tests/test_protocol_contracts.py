from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
TRIGGERS_PATH = ROOT / "data" / "triggers" / "default_triggers.yaml"
EVAL_PATH = ROOT / "data" / "eval" / "eval_dataset.jsonl"
ALLOWED_DECISIONS = {"trigger", "no_trigger", "ask_clarification"}


def _load_triggers() -> list[dict[str, Any]]:
    obj = yaml.safe_load(TRIGGERS_PATH.read_text(encoding="utf-8"))
    assert isinstance(obj, dict), "trigger file must be a mapping"
    triggers = obj.get("triggers")
    assert isinstance(triggers, list), "triggers must be a list"
    return triggers


def _load_eval_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with EVAL_PATH.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            raw = line.strip()
            assert raw, f"eval row {i} is empty"
            rows.append(json.loads(raw))
    return rows


def test_trigger_ids_unique() -> None:
    triggers = _load_triggers()
    ids = [str(t.get("trigger_id") or "").strip() for t in triggers]
    assert all(ids), "all triggers must have non-empty trigger_id"
    assert len(ids) == len(set(ids)), "trigger_id must be unique"


def test_trigger_required_fields_exist() -> None:
    required_fields = {
        "trigger_id",
        "name",
        "description",
        "aliases",
        "positive_examples",
        "negative_examples",
        "required_slots",
        "optional_slots",
        "enabled",
        "tags",
    }
    for trig in _load_triggers():
        assert required_fields.issubset(trig.keys()), f"missing fields in trigger={trig.get('trigger_id')}"
        assert isinstance(trig["aliases"], list)
        assert isinstance(trig["positive_examples"], list)
        assert isinstance(trig["negative_examples"], list)
        assert isinstance(trig["required_slots"], list)
        assert isinstance(trig["optional_slots"], list)
        assert isinstance(trig["enabled"], bool)
        assert isinstance(trig["tags"], list)


def test_slot_format_is_valid() -> None:
    for trig in _load_triggers():
        for slot in [*trig["required_slots"], *trig["optional_slots"]]:
            assert isinstance(slot, dict), "slot must be dict"
            assert str(slot.get("slot_name") or "").strip(), "slot_name is required"
            assert str(slot.get("slot_type") or "").strip(), "slot_type is required"
            assert isinstance(slot.get("required"), bool), "slot.required must be bool"


def test_eval_rows_basic_validity() -> None:
    rows = _load_eval_rows()
    assert len(rows) >= 100, "eval dataset must contain at least 100 rows"
    for i, row in enumerate(rows, start=1):
        query = str(row.get("query") or "").strip()
        decision = str(row.get("expected_decision") or "").strip()
        assert query, f"row {i}: query cannot be empty"
        assert decision in ALLOWED_DECISIONS, f"row {i}: invalid decision={decision}"
        if decision == "trigger":
            assert str(row.get("expected_trigger") or "").strip(), f"row {i}: trigger rows must have expected_trigger"


def test_eval_expected_trigger_refers_to_registry() -> None:
    trigger_ids = {t["trigger_id"] for t in _load_triggers()}
    for i, row in enumerate(_load_eval_rows(), start=1):
        expected = str(row.get("expected_trigger") or "").strip()
        if expected:
            assert expected in trigger_ids, f"row {i}: expected_trigger={expected} not found"


def test_engine_result_contract_shape_stub() -> None:
    # Contract test uses a stub payload and does not depend on concrete engine implementation.
    payload = {
        "user_query": "示例",
        "decision": "trigger",
        "selected_trigger": "set_reminder",
        "confidence": 0.9,
        "candidates": [
            {
                "trigger_id": "set_reminder",
                "recall_score": 0.91,
                "rerank_score": 0.88,
                "final_score": 0.89,
                "notes": "ok",
            }
        ],
        "extracted_slots": {"time": "明天 3 点"},
        "missing_slots": [],
        "clarification_question": None,
        "reasons": ["top1 above threshold"],
        "debug": {"top1": 0.89},
    }
    expected_keys = {
        "user_query",
        "decision",
        "selected_trigger",
        "confidence",
        "candidates",
        "extracted_slots",
        "missing_slots",
        "clarification_question",
        "reasons",
        "debug",
    }
    assert expected_keys.issubset(payload.keys())
    assert payload["decision"] in ALLOWED_DECISIONS
    assert isinstance(payload["candidates"], list)
    assert isinstance(payload["debug"], dict)
