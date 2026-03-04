from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


rd = _load(ROOT / "rag_offline" / "replay_data.py", "replay_data_test")


class ReplayDataTests(unittest.TestCase):
    def test_enrich_sessions_attach_triplets(self):
        sessions = [
            {"query": "q1", "triplet_generated": True},
            {"query": "q2", "triplet_generated": False},
            {"query": "q3", "triplet_generated": True},
        ]
        triplets = [
            {"query": "q1", "positive": "a", "negative": "b"},
            {"query": "q3", "positive": "c", "negative": "d"},
        ]
        rows = rd.enrich_sessions(sessions, triplets)
        self.assertEqual(rows[0]["_triplet"]["query"], "q1")
        self.assertIsNone(rows[1]["_triplet"])
        self.assertEqual(rows[2]["_triplet"]["query"], "q3")

    def test_filter_sessions(self):
        rows = [
            {"query": "hello", "retrieved": ["a"], "feedback": "good", "feedback_signal": 1, "retrieval_used": True},
            {"query": "bye", "retrieved": ["b"], "feedback": "bad", "feedback_signal": -1, "retrieval_used": False},
        ]
        out = rd.filter_sessions(rows, keyword="hello")
        self.assertEqual(len(out), 1)
        out2 = rd.filter_sessions(rows, signal=-1, retrieval_used=False)
        self.assertEqual(len(out2), 1)
        self.assertEqual(out2[0]["query"], "bye")

    def test_summarize_sessions(self):
        rows = [
            {"feedback_signal": 1, "retrieval_used": True, "triplet_generated": True},
            {"feedback_signal": -1, "retrieval_used": False, "triplet_generated": False},
            {"feedback_signal": 0, "retrieval_used": True, "triplet_generated": False},
        ]
        s = rd.summarize_sessions(rows)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["feedback_pos"], 1)
        self.assertEqual(s["feedback_neg"], 1)
        self.assertEqual(s["feedback_neu"], 1)
        self.assertEqual(s["retrieval_used"], 2)
        self.assertEqual(s["triplet_generated"], 1)


if __name__ == "__main__":
    unittest.main()
