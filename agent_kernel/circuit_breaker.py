from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CircuitBreakEvent:
    triggered: bool
    reason: str = ""
    subgoal_id: str = ""
    details: Dict[str, object] = field(default_factory=dict)


class CircuitBreaker:
    def __init__(
        self,
        *,
        same_error_limit: int = 2,
        same_action_replan_limit: int = 3,
        stagnation_cycle_limit: int = 10,
        stagnation_seconds: int = 120,
    ) -> None:
        self.same_error_limit = max(2, int(same_error_limit))
        self.same_action_replan_limit = max(2, int(same_action_replan_limit))
        self.stagnation_cycle_limit = max(2, int(stagnation_cycle_limit))
        self.stagnation_seconds = max(10, int(stagnation_seconds))
        self._error_streaks: Dict[str, Dict[str, int]] = {}
        self._action_streaks: Dict[str, Dict[str, int]] = {}
        self._last_done_cycle = 0
        self._last_done_ts = time.time()

    def mark_done_progress(self, *, cycle: int, ts: Optional[float] = None) -> None:
        self._last_done_cycle = max(self._last_done_cycle, int(cycle))
        self._last_done_ts = float(ts if ts is not None else time.time())

    def on_error(self, *, subgoal_id: str, fingerprint: str) -> CircuitBreakEvent:
        key = str(subgoal_id or "")
        fp = str(fingerprint or "")
        d = self._error_streaks.setdefault(key, {})
        d[fp] = int(d.get(fp, 0)) + 1
        for old_fp in list(d.keys()):
            if old_fp != fp:
                d[old_fp] = 0
        if int(d.get(fp, 0)) >= self.same_error_limit:
            return CircuitBreakEvent(
                triggered=True,
                reason="same_error_repeated",
                subgoal_id=key,
                details={"fingerprint": fp, "count": int(d.get(fp, 0))},
            )
        return CircuitBreakEvent(triggered=False)

    def on_replan_action(self, *, path_key: str, action_fingerprint: str) -> CircuitBreakEvent:
        key = str(path_key or "")
        fp = str(action_fingerprint or "")
        d = self._action_streaks.setdefault(key, {})
        d[fp] = int(d.get(fp, 0)) + 1
        for old_fp in list(d.keys()):
            if old_fp != fp:
                d[old_fp] = 0
        if int(d.get(fp, 0)) >= self.same_action_replan_limit:
            return CircuitBreakEvent(
                triggered=True,
                reason="same_replan_action_loop",
                subgoal_id=key,
                details={"action_fingerprint": fp, "count": int(d.get(fp, 0))},
            )
        return CircuitBreakEvent(triggered=False)

    def check_stagnation(self, *, cycle: int, now_ts: Optional[float] = None) -> CircuitBreakEvent:
        now = float(now_ts if now_ts is not None else time.time())
        cycle_gap = int(cycle) - int(self._last_done_cycle)
        sec_gap = now - float(self._last_done_ts)
        if cycle_gap >= self.stagnation_cycle_limit or sec_gap >= self.stagnation_seconds:
            return CircuitBreakEvent(
                triggered=True,
                reason="no_done_progress",
                details={
                    "cycle_gap": cycle_gap,
                    "seconds_gap": round(sec_gap, 3),
                    "stagnation_cycle_limit": self.stagnation_cycle_limit,
                    "stagnation_seconds": self.stagnation_seconds,
                },
            )
        return CircuitBreakEvent(triggered=False)

    @staticmethod
    def build_diagnostic_report(
        *,
        error_fingerprints: List[str],
        replan_actions: List[str],
        blocked_preconditions: List[str],
        unmet_success_criteria: List[str],
    ) -> Dict[str, object]:
        return {
            "error_fingerprints": [str(x) for x in error_fingerprints[-20:]],
            "replan_actions": [str(x) for x in replan_actions[-20:]],
            "blocked_preconditions": [str(x) for x in blocked_preconditions[-20:]],
            "unmet_success_criteria": [str(x) for x in unmet_success_criteria[-20:]],
        }

