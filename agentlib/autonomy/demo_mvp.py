from __future__ import annotations

from .mock_components import MockEvaluator, MockExecutor, MockPlanner, MockReflector
from .models import Goal
from .orchestrator import Orchestrator
from .store import InMemoryStateStore
from .tool_registry import InMemoryToolRegistry
from .tracing import console_trace_hook


def main() -> None:
    store = InMemoryStateStore()
    tools = InMemoryToolRegistry()

    tools.register("mock.fail", lambda payload: (_ for _ in ()).throw(RuntimeError("simulated tool failure")))
    tools.register("mock.success", lambda payload: f"ok: completed -> {payload[:60]}")

    orch = Orchestrator(
        planner=MockPlanner(),
        executor=MockExecutor(),
        evaluator=MockEvaluator(),
        reflector=MockReflector(),
        tools=tools,
        store=store,
        trace_hooks=[console_trace_hook],
    )

    goal = Goal(objective="MVP demo: recover from failed tool and finish with fallback.")
    summary = orch.run_goal(goal, max_cycles=10)

    print("\n=== SUMMARY ===")
    print(summary)
    print("final_state:", store.state)
    print("tasks:", [(t.title, t.status, t.attempt_count, t.tool_name) for t in store.list_tasks(goal.id)])


if __name__ == "__main__":
    main()

