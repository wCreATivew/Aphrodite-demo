import json
from pathlib import Path

from src.interpreter import InputInterpreter


def _case(name):
    return json.loads(Path(f"tests/golden_cases/{name}.json").read_text())


def test_engineering_route_check():
    c = _case("engineering_route_check")
    out = InputInterpreter().interpret(c["input"])
    assert out["semantic_event"]["event_type"] in set(c["expected"]["event_type_any"])
    assert out["semantic_event"]["topic"] == c["expected"]["topic"]


def test_visual_direction_negative():
    c = _case("visual_direction_negative")
    out = InputInterpreter().interpret(c["input"])
    assert out["semantic_event"]["event_type"] == c["expected"]["event_type"]
    assert out["semantic_event"]["topic"] == c["expected"]["topic"]


def test_correction_and_supplement():
    corr = InputInterpreter().interpret(_case("correction_visual_vs_engineering")["input"])
    sup = InputInterpreter().interpret(_case("supplement_previous_instruction")["input"])
    assert corr["semantic_event"]["event_type"] == "correction"
    assert sup["semantic_event"]["event_type"] == "supplement"


def test_dependency_and_uncertainty_split():
    dep = InputInterpreter().interpret(_case("strong_dependency_boundary")["input"])
    unc = InputInterpreter().interpret(_case("mild_emotional_uncertainty")["input"])
    assert dep["boundary_signal"]["needs_boundary"] is True
    assert unc["semantic_event"]["event_type"] != "dependency_expression"
