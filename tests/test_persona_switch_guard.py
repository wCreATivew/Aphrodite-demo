from __future__ import annotations

import unittest
from unittest.mock import patch

from agentlib.persona_router import PersonaRouteDecision
from agentlib.runtime_engine import RuntimeEngine


class PersonaSwitchGuardTests(unittest.TestCase):
    def test_auto_switch_blocks_low_margin_even_with_high_confidence(self):
        e = RuntimeEngine()
        e.persona_name = "aphrodite"
        e.persona_switch_min_margin = 0.20
        e.cfg.persona_switch_min_confidence = 0.60
        e.turn_index = 10

        low_margin = PersonaRouteDecision(
            persona="codex5.2",
            confidence=0.93,
            reason="test low margin",
            scores={"codex5.2": 0.91, "analyst": 0.87, "coach": 0.12, "aphrodite": 0.10},
        )
        with patch("agentlib.runtime_engine.detect_persona_from_text", return_value=low_margin):
            e._maybe_auto_switch_persona("please patch this bug")

        self.assertEqual(e.persona_name, "aphrodite")
        self.assertAlmostEqual(float(e.mon.get("persona_auto_margin", 0.0)), 0.04, places=4)

    def test_auto_switch_allows_when_confidence_and_margin_are_both_high(self):
        e = RuntimeEngine()
        e.persona_name = "aphrodite"
        e.persona_switch_min_margin = 0.10
        e.cfg.persona_switch_min_confidence = 0.60
        e.turn_index = 10

        high_margin = PersonaRouteDecision(
            persona="codex5.2",
            confidence=0.92,
            reason="test high margin",
            scores={"codex5.2": 1.08, "analyst": 0.78, "coach": 0.22, "aphrodite": 0.11},
        )
        with patch("agentlib.runtime_engine.detect_persona_from_text", return_value=high_margin):
            e._maybe_auto_switch_persona("please patch this bug")

        self.assertEqual(e.persona_name, "codex5.2")
        self.assertGreaterEqual(float(e.mon.get("persona_auto_margin", 0.0)), 0.29)


if __name__ == "__main__":
    unittest.main()
