from __future__ import annotations

import unittest

from agent_kernel.local_replan import apply_local_replan, compute_descendants
from agent_kernel.schemas import ExecutableSubgoal, RetryPolicy, SubgoalState


class LocalReplanTests(unittest.TestCase):
    def test_replaces_failed_node_and_descendants_but_keeps_done(self):
        a = ExecutableSubgoal(
            id="a",
            intent="a",
            executor_type="code_task",
            tool_name="code_task",
            retry_policy=RetryPolicy(),
            state=SubgoalState.DONE,
        )
        b = ExecutableSubgoal(
            id="b",
            intent="b",
            executor_type="code_task",
            tool_name="code_task",
            dependencies=["a"],
            retry_policy=RetryPolicy(),
            state=SubgoalState.FAILED_RETRYABLE,
        )
        c = ExecutableSubgoal(
            id="c",
            intent="c",
            executor_type="code_task",
            tool_name="code_task",
            dependencies=["b"],
            retry_policy=RetryPolicy(),
            state=SubgoalState.READY,
        )
        repl = ExecutableSubgoal(
            id="b2",
            intent="b2",
            executor_type="plan_goal",
            tool_name="plan_goal",
            retry_policy=RetryPolicy(),
        )
        out = apply_local_replan(current=[a, b, c], failed_id="b", replacements=[repl])
        ids = {x.id for x in out}
        self.assertIn("a", ids)
        self.assertIn("b2", ids)
        self.assertNotIn("b", ids)
        self.assertNotIn("c", ids)

    def test_descendants(self):
        nodes = [
            ExecutableSubgoal(id="a", intent="", executor_type="x", tool_name="x", retry_policy=RetryPolicy()),
            ExecutableSubgoal(
                id="b",
                intent="",
                executor_type="x",
                tool_name="x",
                dependencies=["a"],
                retry_policy=RetryPolicy(),
            ),
            ExecutableSubgoal(
                id="c",
                intent="",
                executor_type="x",
                tool_name="x",
                dependencies=["b"],
                retry_policy=RetryPolicy(),
            ),
        ]
        self.assertEqual(compute_descendants(nodes, "b"), {"b", "c"})


if __name__ == "__main__":
    unittest.main()

