from __future__ import annotations

import unittest

from agent_kernel.failure_router import classify_failure


class FailureRouterTests(unittest.TestCase):
    def test_missing_input_routes_to_ask_user(self):
        d = classify_failure(
            subgoal_id="s1",
            tool_name="code_task",
            error_message="missing required input: user_id",
            prior_fingerprints=[],
        )
        self.assertEqual(d.category.value, "missing_input")
        self.assertEqual(d.action.value, "ask_user")

    def test_transient_routes_to_retry(self):
        d = classify_failure(
            subgoal_id="s1",
            tool_name="code_task",
            error_message="TimeoutError: backend timeout",
            prior_fingerprints=[],
        )
        self.assertEqual(d.category.value, "transient_tool_error")
        self.assertEqual(d.action.value, "retry")

    def test_auth_routes_to_repair_auth(self):
        d = classify_failure(
            subgoal_id="s1",
            tool_name="code_task",
            error_message="401 unauthorized token missing",
            prior_fingerprints=[],
        )
        self.assertEqual(d.category.value, "auth_error")
        self.assertEqual(d.action.value, "repair_auth")

    def test_repeated_same_error_routes_to_circuit_break(self):
        first = classify_failure(
            subgoal_id="s1",
            tool_name="code_task",
            error_message="logic conflict",
            prior_fingerprints=[],
        )
        second = classify_failure(
            subgoal_id="s1",
            tool_name="code_task",
            error_message="logic conflict",
            prior_fingerprints=[first.fingerprint],
        )
        self.assertEqual(second.category.value, "repeated_same_error")
        self.assertEqual(second.action.value, "circuit_break")


if __name__ == "__main__":
    unittest.main()

