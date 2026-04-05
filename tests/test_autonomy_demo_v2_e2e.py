from agentlib.autonomy.demo_v2 import (
    _CALLS,
    DemoEvaluator,
    DemoExecutor,
    DemoPlanner,
    DemoReflector,
    Goal,
    Orchestrator,
)
from agentlib.autonomy.perception.audio_adapter import AudioAdapter
from agentlib.autonomy.perception.fusion import PerceptionFusionEngine
from agentlib.autonomy.perception.olfactory_adapter import OlfactoryAdapter
from agentlib.autonomy.perception.tactile_adapter import TactileAdapter
from agentlib.autonomy.perception.vision_adapter import VisionAdapter
from agentlib.autonomy.store import InMemoryStateStore
from agentlib.autonomy.tool_registry import InMemoryToolRegistry


def test_demo_v2_mainline_e2e_with_perception_cycle() -> None:
    _CALLS.clear()

    store = InMemoryStateStore()
    tools = InMemoryToolRegistry()
    tools.register("tool.fetch_context", lambda payload: f"ok:context:{payload}", schema={"required": ["query"]})

    def _exec(payload: str) -> str:
        _CALLS["tool.exec_code"] += 1
        if _CALLS["tool.exec_code"] <= 2:
            raise RuntimeError("TimeoutError: transient backend timeout")
        return f"ok:exec:{payload}"

    tools.register("tool.exec_code", _exec, schema={"required": ["code_ref"]})
    tools.register(
        "tool.auth_api",
        lambda _payload: (_ for _ in ()).throw(PermissionError("401 Unauthorized: missing token")),
        schema={"required": ["endpoint"]},
    )

    orch = Orchestrator(
        planner=DemoPlanner(),
        executor=DemoExecutor(),
        evaluator=DemoEvaluator(),
        reflector=DemoReflector(),
        tools=tools,
        store=store,
        trace_hooks=[],
    )

    # Mainline orchestrator expects perception adapters/fusion engine to be present.
    orch._adapters = [VisionAdapter(), AudioAdapter(), TactileAdapter(), OlfactoryAdapter()]  # noqa: SLF001
    orch.perception_fusion = PerceptionFusionEngine()  # noqa: SLF001

    summary = orch.run_goal(Goal(objective="demo_v2 e2e"), max_cycles=20)

    assert summary["cycles"] >= 1
    assert summary["done"] >= 1
    assert summary["traces"] > 0

    latest = store.latest_perception
    assert latest
    assert latest["degraded"] is False
    assert len(latest["aligned_events"]) >= 4

    # exec path should retry before success.
    assert _CALLS["tool.exec_code"] >= 2
