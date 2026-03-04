from __future__ import annotations

from router.llm_router import RouterAction, RouterOutput, RouterScope, route_intent


class _FakeClient:
    def __init__(self, text: str):
        self.text = text

    def chat(self, messages, temperature=0.1, max_tokens=240):
        return self.text


def test_route_intent_normalizes_json_output() -> None:
    client = _FakeClient('{"action":"execute_light","scope":"project_only","needs_confirm":true,"reason":"write file","confidence":0.88}')
    out = route_intent(user_message='请修改项目代码', llm_client=client)
    assert out.action == RouterAction.EXECUTE_LIGHT.value
    assert out.scope == RouterScope.PROJECT_ONLY.value
    assert out.needs_confirm is True
    assert 0.0 <= out.confidence <= 1.0


def test_route_intent_falls_back_when_invalid_json() -> None:
    client = _FakeClient('not json')
    out = route_intent(user_message='帮我查一下文档', llm_client=client)
    assert isinstance(out, RouterOutput)
    assert out.action in {x.value for x in RouterAction}


def test_route_intent_empty_message_returns_chat() -> None:
    out = route_intent(user_message='')
    assert out.action == RouterAction.CHAT.value
    assert out.scope == RouterScope.MAIN.value
