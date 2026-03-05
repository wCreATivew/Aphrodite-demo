from __future__ import annotations

from agentlib.runtime_engine import RuntimeEngine


def test_low_confidence_non_control_uses_conservative_clarify() -> None:
    e = RuntimeEngine()
    out = e._semantic_guard_decision(
        text="现在帮我做一份清单，内容是检查程序中可能出错的链路，返回给我",
        intent="chat",
        suggested_mode="chat",
        confidence=0.12,
    )
    assert str(out.get("suggested_mode") or "") == "ask_clarify"
    assert str(out.get("reason") or "").startswith("low_confidence_non_control<")


def test_low_confidence_high_risk_still_requires_confirmation() -> None:
    e = RuntimeEngine()
    out = e._semantic_guard_decision(
        text="请开启 selfdrive 自动推进去修复整个系统",
        intent="code_debug",
        suggested_mode="selfdrive",
        confidence=0.12,
    )
    assert str(out.get("suggested_mode") or "") == "ask_user_confirm"
