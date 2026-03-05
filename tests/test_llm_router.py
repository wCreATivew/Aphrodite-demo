from agentlib.router.llm_router import LLMRouter, RouterStateMachine, RouterOutput


def test_router_output_actions_in_5_classes() -> None:
    r = LLMRouter()
    out = r.route(user_message="帮我删除仓库里的临时文件并提交")
    assert out.action in {"CHAT", "ASK_CLARIFY", "TOOL_LIGHT", "EXECUTE_LIGHT", "EXECUTE_HEAVY"}


def test_router_gate_requires_confirm_for_restricted_execute() -> None:
    sm = RouterStateMachine()
    out = RouterOutput(
        action="EXECUTE_HEAVY",
        scope="PROJECT_ONLY",
        needs_confirm=True,
        reason="sensitive",
        confidence=0.9,
    )
    gated = sm.apply(out, confirmed=False)
    assert gated.action == "ASK_CLARIFY"
    assert gated.needs_confirm is True


def test_router_gate_passes_when_confirmed() -> None:
    sm = RouterStateMachine()
    out = RouterOutput(
        action="EXECUTE_LIGHT",
        scope="ISOLATED",
        needs_confirm=True,
        reason="sensitive",
        confidence=0.8,
    )
    gated = sm.apply(out, confirmed=True)
    assert gated.action == "EXECUTE_LIGHT"
