from agentlib.router.llm_router import LLMRouter


def test_ambiguous_request_prefers_ask_clarify_over_chat() -> None:
    r = LLMRouter()
    out = r.route(user_message="你帮我想想办法")
    assert out.action == "ASK_CLARIFY"


def test_state_change_task_is_execute_light() -> None:
    r = LLMRouter()
    out = r.route(user_message="帮我修一下这个仓库里的构建报错")
    assert out.action == "EXECUTE_LIGHT"


def test_scope_defaults_to_main_when_no_explicit_domain() -> None:
    r = LLMRouter()
    out = r.route(user_message="帮我总结一下这个方案的优缺点")
    assert out.scope == "MAIN"


def test_scope_project_only_when_repo_explicit() -> None:
    r = LLMRouter()
    out = r.route(user_message="帮我看看这个仓库是做什么的")
    assert out.scope == "PROJECT_ONLY"


def test_high_impact_operation_requires_confirm() -> None:
    r = LLMRouter()
    out = r.route(user_message="帮我删除项目里旧分支并推送")
    assert out.needs_confirm is True


def test_world_change_with_uncertain_scope_defaults_confirm_true() -> None:
    r = LLMRouter()
    out = r.route(user_message="帮我修改配置并应用")
    assert out.action == "EXECUTE_LIGHT"
    assert out.needs_confirm is True


def test_world_change_with_limited_rollbackable_scope_can_skip_confirm() -> None:
    r = LLMRouter()
    out = r.route(user_message="只改这个文件，先模拟，可回滚")
    assert out.action in {"EXECUTE_LIGHT", "EXECUTE_HEAVY"}
    assert out.needs_confirm is False
