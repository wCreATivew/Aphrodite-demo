from __future__ import annotations

import unittest

from agent_kernel.kernel import AgentKernel
from agent_kernel.schemas import AgentState, Task
from agent_kernel.worker import SimpleWorker


class FSMSchedulerTests(unittest.TestCase):
    def test_retry_then_done_without_global_fallback(self):
        kernel = AgentKernel(worker=SimpleWorker())
        state = AgentState(
            goal="retry test",
            tasks=[
                Task(
                    task_id="t1",
                    kind="code_task",
                    description="unstable",
                    input_payload={
                        "force_fail": True,
                        "retry_policy": {"max_attempts": 3, "backoff": "exponential", "base_delay_ms": 100},
                    },
                    status="draft",
                )
            ],
            budget_steps_max=8,
        )
        out = kernel.run(state=state, checkpoint_path="outputs/test_fsm_scheduler_checkpoint.json")
        self.assertEqual(out.status, "done")
        self.assertTrue(out.goal_done)
        self.assertEqual(out.tasks[0].status, "done")
        routed = [e for e in out.trace if str((e or {}).get("event")) == "failure_routed"]
        self.assertGreaterEqual(len(routed), 1)


if __name__ == "__main__":
    unittest.main()

