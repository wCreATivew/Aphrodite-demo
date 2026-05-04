from agentlib.runtime_engine import RuntimeEngine


def test_presence_flow_uses_interpreter_schema():
    tr = RuntimeEngine()._presence_min_flow(user_text="帮我检查这个 runtime 入口是不是接对了。", assistant_text="先看入口函数", trace_id="x", event_id="y")
    ie = tr["interpreted_event"]
    assert "semantic_event" in ie and "performance_signal" in ie and "boundary_signal" in ie


def test_interpreter_failure_fallback(monkeypatch):
    eng = RuntimeEngine()
    monkeypatch.setattr(eng.input_interpreter, "interpret", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("x")))
    tr = eng._presence_min_flow(user_text="hi", assistant_text="ok", trace_id="x1", event_id="y1")
    assert tr["interpreted_event"]["semantic_event"]["event_type"] == "unknown"
    assert "interpreter_failed" in tr["interpreted_event"]["warnings"]
