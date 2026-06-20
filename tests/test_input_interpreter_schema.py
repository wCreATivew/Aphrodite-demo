from src.interpreter.input_interpreter import InputInterpreter
from src.interpreter.schema import unknown_output


def test_schema_complete_and_clipped_numeric_fields():
    it = InputInterpreter()
    out = it.interpret("python bug")
    for k in ["semantic_event", "relationship_signal", "boundary_signal", "memory_trigger_signal", "performance_signal", "confidence", "warnings"]:
        assert k in out
    numeric_checks = [
        ("relationship_signal", "dependency_risk"),
        ("relationship_signal", "vulnerability_relevance"),
        ("relationship_signal", "carefulness"),
        ("relationship_signal", "boundary_sensitivity"),
        ("boundary_signal", "external_pollution_risk"),
        ("boundary_signal", "internal_tension_relevance"),
        ("boundary_signal", "direct_fulfillment_risk"),
        ("memory_trigger_signal", "memory_relevance"),
        ("memory_trigger_signal", "recall_importance"),
    ]
    for sec, key in numeric_checks:
        v = float(out[sec][key])
        assert 0.0 <= v <= 1.0


def test_unknown_output_compatibility_contract_preserves_warnings():
    out = unknown_output(["interpreter_failed"])
    assert out["semantic_event"]["type"] == "unknown"
    assert out["memory_trigger_signal"]["memory_type"] == "none"
    assert out["confidence"]["event"] == 0.3
    assert out["warnings"] == ["interpreter_failed"]
