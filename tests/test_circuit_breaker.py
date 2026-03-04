from __future__ import annotations

import unittest

from agent_kernel.circuit_breaker import CircuitBreaker


class CircuitBreakerTests(unittest.TestCase):
    def test_same_error_trip(self):
        cb = CircuitBreaker(same_error_limit=2)
        e1 = cb.on_error(subgoal_id="s1", fingerprint="fp")
        e2 = cb.on_error(subgoal_id="s1", fingerprint="fp")
        self.assertFalse(e1.triggered)
        self.assertTrue(e2.triggered)

    def test_replan_loop_trip(self):
        cb = CircuitBreaker(same_action_replan_limit=3)
        self.assertFalse(cb.on_replan_action(path_key="p", action_fingerprint="a").triggered)
        self.assertFalse(cb.on_replan_action(path_key="p", action_fingerprint="a").triggered)
        self.assertTrue(cb.on_replan_action(path_key="p", action_fingerprint="a").triggered)

    def test_stagnation_trip(self):
        cb = CircuitBreaker(stagnation_cycle_limit=2, stagnation_seconds=9999)
        cb.mark_done_progress(cycle=1, ts=0.0)
        e = cb.check_stagnation(cycle=3, now_ts=0.1)
        self.assertTrue(e.triggered)


if __name__ == "__main__":
    unittest.main()

