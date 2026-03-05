from agentlib.semantic_intent_lane import list_semantic_intent_modules


def test_semantic_intent_modules_contains_router_entries() -> None:
    rows = list_semantic_intent_modules()
    names = {str(r.get("name") or "") for r in rows}
    assert "agentlib.router.llm_router" in names
    assert "agentlib.semantic_intent_lane" in names
    assert "agentlib.persona_router" in names
