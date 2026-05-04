import json
from pathlib import Path

from src.interpreter import InputInterpreter


def _case(name):
    return json.loads(Path(f"tests/golden_cases/{name}.json").read_text())


def test_dependency_expression_case():
    c = _case("dependency_expression")
    out = InputInterpreter().interpret(c["input"])
    assert out["semantic_event"]["event_type"] in {"dependency_expression", "boundary_testing"}
    assert out["relationship_signal"]["dependency_risk"] >= c["expected"]["dependency_risk_min"]
    assert out["boundary_signal"]["needs_boundary"] is True


def test_project_origin_case():
    c = _case("project_origin_reference")
    out = InputInterpreter().interpret(c["input"])
    assert out["semantic_event"]["event_type"] == c["expected"]["event_type"]
    assert out["memory_trigger_signal"]["memory_type"] == c["expected"]["memory_type"]


def test_ambiguous_confidence_low():
    c = _case("ambiguous_short_input")
    out = InputInterpreter().interpret(c["input"])
    assert out["confidence"]["overall"] <= c["expected"]["confidence_overall_max"]
