from __future__ import annotations

from agentlib.runtime_engine import RuntimeEngine


def test_immediate_reply_for_clarify_contains_single_question() -> None:
    e = RuntimeEngine()
    text = e.immediate_protocol.compose_immediate_reply("帮我弄这个", {"action": "ASK_CLARIFY"})
    q_count = text.count("？") + text.count("?")
    assert q_count == 1


def test_immediate_reply_for_execute_is_short_ack_only() -> None:
    e = RuntimeEngine()
    text = e.immediate_protocol.compose_immediate_reply("请帮我运行评测", {"action": "EXECUTE_HEAVY"})
    assert "```" not in text
    assert "1." not in text and "步骤" not in text
    assert len(text) <= 24


def test_send_immediate_reply_sets_trace_fields() -> None:
    e = RuntimeEngine()
    packet = e.immediate_protocol.send(
        user_text="你能安慰我一下吗",
        msg_id=None,
        router=e.semantic_intent_lane.router,
        state_machine=e.semantic_intent_lane.state_machine,
        emit_reply=e._emit_reply,
        mon=e.mon,
    )
    assert packet.action
    assert int(e.mon.get("immediate_reply_sent", 0) or 0) == 1
    assert float(e.mon.get("sent_at_timestamp") or 0.0) > 0
    assert str(e.mon.get("route_decision") or "")


def test_execute_event_checks_immediate_reply_order() -> None:
    e = RuntimeEngine()
    _ = e.immediate_protocol.send(
        user_text="请开始自推进",
        msg_id=None,
        router=e.semantic_intent_lane.router,
        state_machine=e.semantic_intent_lane.state_machine,
        emit_reply=e._emit_reply,
        mon=e.mon,
    )
    before = int(e.mon.get("immediate_reply_order_violation", 0) or 0)
    _ = e._execute_selfdrive_control_dsl({"command": "STATUS_SELFDRIVE", "args": {}}, source_text="status")
    after = int(e.mon.get("immediate_reply_order_violation", 0) or 0)
    assert after == before


def test_send_prefers_fastgate_for_chat_route() -> None:
    class _FG:
        def infer(self, _: str):
            return type("_FGOut", (), {"route": "CHAT"})()

    class _Router:
        def __init__(self):
            self.fast_gate = _FG()

        def route(self, **_: object):
            raise AssertionError("router.route should not be called when fastgate says CHAT")

    class _SM:
        def apply(self, route, confirmed=False):
            return route

    sent = {}

    def _emit_reply(**kwargs):
        sent.update(kwargs)

    proto = RuntimeEngine().immediate_protocol
    mon = {}
    out = proto.send(
        user_text="你好",
        msg_id=None,
        router=_Router(),
        state_machine=_SM(),
        emit_reply=_emit_reply,
        mon=mon,
    )

    assert out.action == "CHAT"
    assert mon.get("immediate_reply_route_source") == "fast_gate"
    assert str(sent.get("reply_text") or "")
