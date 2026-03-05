from agentlib.coach import Coach


def test_coach_oneshot_when_gap_high() -> None:
    c = Coach()
    d = c.decide("请帮我整理学习计划", "TOOL_LIGHT", ["planner"])
    assert d.mode == "ONESHOT"
    assert d.gap >= 0.25


def test_coach_budgeted_when_gap_low() -> None:
    c = Coach()
    d = c.decide("请配置复杂环境", "EXECUTE_HEAVY", ["env_manager", "unknown_tool"])
    assert d.mode == "BUDGETED"
    assert d.gap < 0.25
    assert d.budget_initial <= 1.0


def test_coach_learning_gap_reports_missing_tools() -> None:
    c = Coach()
    d = c.decide("task", "EXECUTE_LIGHT", ["planner", "new_tool_x"])
    assert "new_tool_x" in d.learning_gap
