from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    import sys

    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


cu = _load(ROOT / "rag_offline" / "conversation_utils.py", "conversation_utils_test")
ui = _load(ROOT / "rag_offline" / "unlabeled_ingest.py", "unlabeled_ingest_test")


class ConversationUtilsTests(unittest.TestCase):
    def test_infer_feedback_signal(self):
        self.assertEqual(cu.infer_feedback_signal("good answer"), 1)
        self.assertEqual(cu.infer_feedback_signal("this is wrong"), -1)
        self.assertEqual(cu.infer_feedback_signal("maybe"), 0)

    def test_pick_pseudo_triplet_positive(self):
        t = cu.pick_pseudo_triplet(
            query="q",
            retrieved_docs=["a", "b"],
            corpus_docs=["a", "b", "c", "d"],
            feedback_signal=1,
        )
        self.assertIsNotNone(t)
        assert t is not None
        self.assertEqual(t["query"], "q")
        self.assertEqual(t["positive"], "a")
        self.assertIn(t["negative"], {"c", "d"})


class UnlabeledIngestTests(unittest.TestCase):
    def test_chunk_text(self):
        s = "x" * 1000
        chunks = ui.chunk_text(s, chunk_size=200, overlap=50)
        self.assertGreaterEqual(len(chunks), 4)

    def test_ingest_text_file(self):
        p = ROOT / "rag_offline" / "README.md"
        docs = ui.ingest_paths([str(p)], chunk_size=120, chunk_overlap=20)
        self.assertGreater(len(docs), 1)
        self.assertTrue(all(d.source.endswith("README.md") for d in docs))


if __name__ == "__main__":
    unittest.main()
