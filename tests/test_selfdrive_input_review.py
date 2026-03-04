from __future__ import annotations

from agentlib.runtime_engine import RuntimeEngine


def test_selfdrive_start_requires_confirmation_when_permissions_limited() -> None:
    e = RuntimeEngine()
    e.cfg.full_user_permissions = False
    out = e._execute_selfdrive_control_dsl(
        {"command": "START_SELFDRIVE", "args": {"goal": "修复代理模块并补充测试"}},
        source_text="请你自主推进修复代理模块并补充测试",
    )
    assert isinstance(out, str)
    assert "权限确认" in out
    assert int(e.mon.get("guard_confirm_pending", 0) or 0) == 1


def test_selfdrive_start_rejects_non_executable_goal() -> None:
    e = RuntimeEngine()
    out = e._execute_selfdrive_control_dsl(
        {"command": "START_SELFDRIVE", "args": {"goal": "随便做点什么"}},
        source_text="随便做点什么",
    )
    assert isinstance(out, str)
    assert "goal_not_executable" in out


def test_confirmed_selfdrive_start_does_not_loop_on_permission_review() -> None:
    e = RuntimeEngine()
    e.cfg.full_user_permissions = False
    first = e._handle_natural_language_control("请你自主推进修复代理模块并补充测试")
    assert isinstance(first, str)
    assert "权限确认" in first
    second = e._handle_natural_language_control("确认执行")
    assert isinstance(second, str)
    assert "[selfdrive] started" in second


def test_confirmed_selfdrive_keeps_budget_from_source_text() -> None:
    e = RuntimeEngine()
    e.cfg.full_user_permissions = False
    _ = e._handle_natural_language_control("请你自主推进修复代理模块并补充测试 30分钟")
    out = e._handle_natural_language_control("确认执行")
    assert isinstance(out, str)
    assert "[selfdrive] started" in out
    assert int(e.mon.get("selfdrive_budget_max", 0) or 0) >= 30
