from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from semantic_trigger.decision import decide
from semantic_trigger.schemas import CandidateScore


class DecisionPolicyThresholdTests(unittest.TestCase):
    def test_high_score_high_margin_trigger(self) -> None:
        out = decide(
            candidates=[
                CandidateScore(trigger_id="set_reminder", final_score=0.82),
                CandidateScore(trigger_id="set_alarm", final_score=0.62),
            ],
            extracted_slots={"time": "tomorrow 8am", "content": "meeting"},
            required_slots=[{"slot_name": "time"}, {"slot_name": "content"}],
            accept_threshold=0.70,
            clarify_threshold=0.45,
            margin_threshold=0.08,
            no_trigger_floor=0.25,
        )
        self.assertEqual(out.decision, "trigger")

    def test_high_score_low_margin_ask_clarification(self) -> None:
        out = decide(
            candidates=[
                CandidateScore(trigger_id="send_message", final_score=0.80),
                CandidateScore(trigger_id="email_draft", final_score=0.78),
            ],
            extracted_slots={"recipient": "John", "content": "Running late"},
            required_slots=[{"slot_name": "recipient"}, {"slot_name": "content"}],
            accept_threshold=0.70,
            clarify_threshold=0.45,
            margin_threshold=0.05,
            no_trigger_floor=0.25,
        )
        self.assertEqual(out.decision, "ask_clarification")
        self.assertIn("small_margin", " ".join(out.reasons))

    def test_mid_score_ask_clarification(self) -> None:
        out = decide(
            candidates=[
                CandidateScore(trigger_id="weather_query", final_score=0.54),
                CandidateScore(trigger_id="web_search", final_score=0.30),
            ],
            extracted_slots={"location": "Seattle"},
            required_slots=[{"slot_name": "location"}],
            accept_threshold=0.65,
            clarify_threshold=0.45,
            margin_threshold=0.08,
            no_trigger_floor=0.25,
        )
        self.assertEqual(out.decision, "ask_clarification")

    def test_low_score_no_trigger(self) -> None:
        out = decide(
            candidates=[
                CandidateScore(trigger_id="send_message", final_score=0.20),
                CandidateScore(trigger_id="email_draft", final_score=0.10),
            ],
            extracted_slots={},
            required_slots=[],
            accept_threshold=0.65,
            clarify_threshold=0.45,
            margin_threshold=0.08,
            no_trigger_floor=0.25,
        )
        self.assertEqual(out.decision, "no_trigger")

    def test_missing_required_slots_ask_clarification(self) -> None:
        out = decide(
            candidates=[
                CandidateScore(trigger_id="set_reminder", final_score=0.88),
                CandidateScore(trigger_id="set_alarm", final_score=0.40),
            ],
            extracted_slots={"time": "tomorrow morning"},
            required_slots=[{"slot_name": "time"}, {"slot_name": "content"}],
            accept_threshold=0.70,
            clarify_threshold=0.45,
            margin_threshold=0.08,
            no_trigger_floor=0.25,
        )
        self.assertEqual(out.decision, "ask_clarification")
        self.assertIn("content", out.missing_slots)

    def test_per_trigger_accept_threshold_override(self) -> None:
        out = decide(
            candidates=[
                CandidateScore(trigger_id="set_reminder", final_score=0.58),
                CandidateScore(trigger_id="set_alarm", final_score=0.30),
            ],
            extracted_slots={"time": "8am", "content": "drink water"},
            required_slots=[{"slot_name": "time"}, {"slot_name": "content"}],
            accept_threshold=0.62,
            clarify_threshold=0.45,
            margin_threshold=0.08,
            no_trigger_floor=0.25,
            per_trigger_accept_threshold={"set_reminder": 0.55},
        )
        self.assertEqual(out.decision, "trigger")


if __name__ == "__main__":
    unittest.main()
