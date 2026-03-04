from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

from agent_kernel.schemas import ExecutableSubgoal, Task

ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {module_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


if "agentlib" not in sys.modules:
    pkg = types.ModuleType("agentlib")
    pkg.__path__ = [str(ROOT / "agentlib")]
    sys.modules["agentlib"] = pkg
if "agentlib.autonomy" not in sys.modules:
    pkg2 = types.ModuleType("agentlib.autonomy")
    pkg2.__path__ = [str(ROOT / "agentlib" / "autonomy")]
    sys.modules["agentlib.autonomy"] = pkg2

_load_module("agentlib.autonomy.interfaces", ROOT / "agentlib" / "autonomy" / "interfaces.py")
_load_module("agentlib.autonomy.models", ROOT / "agentlib" / "autonomy" / "models.py")
_load_module("agentlib.autonomy.state", ROOT / "agentlib" / "autonomy" / "state.py")
_load_module("agentlib.autonomy.store", ROOT / "agentlib" / "autonomy" / "store.py")
_load_module("agentlib.autonomy.tool_registry", ROOT / "agentlib" / "autonomy" / "tool_registry.py")
_load_module("agentlib.autonomy.tracing", ROOT / "agentlib" / "autonomy" / "tracing.py")
mock_mod = _load_module("agentlib.autonomy.mock_components", ROOT / "agentlib" / "autonomy" / "mock_components.py")
orch_mod = _load_module("agentlib.autonomy.orchestrator", ROOT / "agentlib" / "autonomy" / "orchestrator.py")


class DualLayerCompatTests(unittest.TestCase):
    def test_task_subgoal_roundtrip(self):
        task = Task(
            task_id="t1",
            kind="code_task",
            description="do x",
            input_payload={"instruction": "x"},
            status="draft",
        )
        sg = ExecutableSubgoal.from_task(task)
        out = sg.to_task(priority=task.priority)
        self.assertEqual(out.task_id, "t1")
        self.assertEqual(out.kind, "code_task")
        self.assertIn(out.status, {"draft", "ready", "running", "done", "failed_retryable", "blocked", "failed", "skipped"})

    def test_autonomy_orchestrator_terminates_without_infinite_fallback(self):
        store = sys.modules["agentlib.autonomy.store"].InMemoryStateStore()
        tools = sys.modules["agentlib.autonomy.tool_registry"].InMemoryToolRegistry()
        tools.register("mock.fail", lambda payload: (_ for _ in ()).throw(RuntimeError("simulated tool failure")))
        tools.register("mock.success", lambda payload: f"ok: {payload}")
        orch = orch_mod.Orchestrator(
            planner=mock_mod.MockPlanner(),
            executor=mock_mod.MockExecutor(),
            evaluator=mock_mod.MockEvaluator(),
            reflector=mock_mod.MockReflector(),
            tools=tools,
            store=store,
            trace_hooks=[],
        )
        goal = sys.modules["agentlib.autonomy.models"].Goal(objective="compat test")
        summary = orch.run_goal(goal, max_cycles=10)
        self.assertLessEqual(int(summary.get("cycles", 0)), 10)
        self.assertGreaterEqual(int(summary.get("done", 0)), 1)


if __name__ == "__main__":
    unittest.main()

