from __future__ import annotations

import unittest

from agent_kernel.compile_check import plan_compile_check
from agent_kernel.schemas import ExecutableSubgoal, Predicate, RetryPolicy, SuccessCriterion


class _ToolReg:
    def __init__(self):
        self.schemas = {"code_task": {"required": ["instruction"]}}

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.schemas

    def get_tool_schema(self, tool_name: str):
        return self.schemas.get(tool_name, {"required": []})


class PlanCompileCheckTests(unittest.TestCase):
    def test_detects_multiple_compile_issues(self):
        tools = _ToolReg()
        s1 = ExecutableSubgoal(
            id="a",
            intent="x",
            executor_type="code_task",
            tool_name="code_task",
            inputs={},
            dependencies=["b"],
            preconditions=[Predicate(op="unknown_op")],
            success_criteria=[SuccessCriterion(op="tool_output_contains", args={"text": "ok"})],
            retry_policy=None,
            fallback={"on_failure": "a"},
        )
        s2 = ExecutableSubgoal(
            id="b",
            intent="y",
            executor_type="code_task",
            tool_name="missing_tool",
            inputs={"instruction": "do"},
            dependencies=["a"],
            retry_policy=RetryPolicy(),
        )
        issues = plan_compile_check(subgoals=[s1, s2], tools=tools)
        codes = {x.code for x in issues}
        self.assertIn("input_schema_incomplete", codes)
        self.assertIn("tool_not_registered", codes)
        self.assertIn("dependency_cycle", codes)
        self.assertIn("precondition_not_evaluable", codes)
        self.assertIn("fallback_self_loop", codes)
        self.assertIn("retry_policy_missing", codes)


if __name__ == "__main__":
    unittest.main()

