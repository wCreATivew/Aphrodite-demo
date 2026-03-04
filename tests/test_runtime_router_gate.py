from __future__ import annotations

from agentlib.runtime_engine import RuntimeEngine
from router.llm_router import RouterAction, RouterOutput, RouterScope


def test_router_gate_requires_confirm_for_project_scope(monkeypatch) -> None:
    e = RuntimeEngine()

    def _fake_route_intent(**kwargs):
        return RouterOutput(
            action=RouterAction.EXECUTE_LIGHT.value,
            scope=RouterScope.PROJECT_ONLY.value,
            needs_confirm=True,
            reason='write',
            confidence=0.9,
        )

    monkeypatch.setattr('agentlib.runtime_engine.route_intent', _fake_route_intent)
    out = e._handle_natural_language_control('请直接改项目里的代码')
    assert isinstance(out, str)
    assert '确认执行' in out
    assert int(e.mon.get('guard_confirm_pending', 0) or 0) == 1


def test_router_gate_returns_clarify_when_router_asks(monkeypatch) -> None:
    e = RuntimeEngine()

    def _fake_route_intent(**kwargs):
        return RouterOutput(
            action=RouterAction.ASK_CLARIFY.value,
            scope=RouterScope.MAIN.value,
            needs_confirm=False,
            reason='missing slots',
            confidence=0.55,
        )

    monkeypatch.setattr('agentlib.runtime_engine.route_intent', _fake_route_intent)
    out = e._handle_natural_language_control('帮我处理一下')
    assert isinstance(out, str)
    assert '澄清' in out
