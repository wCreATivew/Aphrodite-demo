from agentlib.runtime_engine import RuntimeEngine
from src.interpreter import InputInterpreter


def test_ambiguous_followup_without_context_low_confidence():
    out = InputInterpreter().interpret("对，就这个。")
    assert out["confidence"]["overall"] <= 0.5


def test_ambiguous_followup_with_context_inherits_topic_with_warning():
    out = InputInterpreter().interpret("对，就这个。", context={"previous_topic": "runtime_or_engineering", "previous_event_type": "technical_question"})
    assert out["semantic_event"]["topic"] == "runtime_or_engineering"
    assert "context_inherited" in out["warnings"]


def test_presence_flow_passes_previous_trace_context():
    eng = RuntimeEngine()
    tr1 = eng._presence_min_flow(user_text="这个 runtime 入口是不是接错了？", assistant_text="先看入口", trace_id="t1", event_id="e1")
    eng.mon["presence_last_trace"] = tr1
    tr2 = eng._presence_min_flow(user_text="对，就这个。", assistant_text="收到", trace_id="t2", event_id="e2")
    assert tr2["interpreted_event"]["semantic_event"]["topic"] == "runtime_or_engineering"
