from src.interpreter import InputInterpreter
from src.interpreter.validators import validate_interpreted_event


def test_schema_has_all_top_level_fields():
    out = InputInterpreter().interpret("hello")
    for key in ["semantic_event", "affective_signal", "goal_signal", "relationship_signal", "memory_trigger_signal", "boundary_signal", "performance_signal", "confidence", "warnings"]:
        assert key in out


def test_clipping_and_defaults_work():
    raw = {"affective_signal": {"valence": 9, "arousal": "0.7", "intensity": -1, "uncertainty": float("nan")}}
    out = validate_interpreted_event(raw)
    assert -1 <= out["affective_signal"]["valence"] <= 1
    assert out["affective_signal"]["arousal"] == 0.0
    assert 0 <= out["affective_signal"]["intensity"] <= 1
    assert out["affective_signal"]["uncertainty"] == 0.0
