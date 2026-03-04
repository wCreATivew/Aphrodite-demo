from __future__ import annotations

import importlib.util
import sys
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


prompt_mod = _load_module("agentlib.companion_prompt", ROOT / "agentlib" / "companion_prompt.py")
rag_mod = _load_module("agentlib.companion_rag", ROOT / "agentlib" / "companion_rag.py")


class CompanionPromptTests(unittest.TestCase):
    def test_build_and_render_prompt_sections(self):
        sections = prompt_mod.build_system_prompt_sections(persona="p", style="s")
        rendered = prompt_mod.render_system_prompt(sections)
        self.assertIn("[persona]", rendered)
        self.assertIn("p", rendered)
        self.assertIn("[style]", rendered)


class CompanionRagTests(unittest.TestCase):
    def test_build_rag_context_keyword_match(self):
        kb = ["anxiety grounding breathing", "project planning checklist", "movie recommendation"]
        items = rag_mod.build_rag_context("I need planning for project", kb, top_k=2, rag_mode="keyword")
        self.assertGreaterEqual(len(items), 1)
        self.assertIn("project planning checklist", items[0])

    def test_render_rag_block(self):
        block = rag_mod.render_rag_block(["a", "b"])
        self.assertIn("[retrieval_context]", block)
        self.assertIn("- a", block)

    def test_build_rag_context_embedding_uses_engine(self):
        kb = ["doc a", "doc b"]
        cfg = rag_mod.RagConfig(mode="embedding", self_rag_enabled=False)

        class FakeEngine:
            def sync_docs(self, texts, persist=True):
                return None

            def retrieve_scored(self, query, top_k):
                return [{"text": "doc b", "score": 0.9}]

        with unittest.mock.patch.object(rag_mod, "_get_engine", return_value=FakeEngine()):
            items = rag_mod.build_rag_package("query long", kb, top_k=1, rag_mode="embedding", config=cfg).items
        self.assertEqual(items, ["doc b"])

    def test_build_rag_package_contains_trace(self):
        kb = ["project planning checklist", "breathing guide"]
        cfg = rag_mod.RagConfig(mode="keyword", iterative_enabled=True, iterative_max_queries=2, debug_enabled=True)
        result = rag_mod.build_rag_package(
            user_text="project planning please",
            knowledge_base=kb,
            top_k=1,
            config=cfg,
        )
        self.assertEqual(result.mode_used, "keyword")
        self.assertGreaterEqual(len(result.queries), 1)
        self.assertGreaterEqual(len(result.trace), 1)
        self.assertEqual(result.items[0], "project planning checklist")

    def test_self_rag_can_skip_low_info_turn(self):
        kb = ["project planning checklist", "breathing guide"]
        cfg = rag_mod.RagConfig(mode="keyword", self_rag_enabled=True, self_min_query_chars=3)
        result = rag_mod.build_rag_package(
            user_text="ok",
            knowledge_base=kb,
            top_k=2,
            config=cfg,
        )
        self.assertFalse(result.retrieval_used)
        self.assertEqual(result.items, [])
        self.assertNotEqual(result.skip_reason, "")

    def test_self_rag_second_pass_triggers_when_low_score(self):
        kb = ["x alpha", "y beta", "z gamma"]
        cfg = rag_mod.RagConfig(
            mode="keyword",
            self_rag_enabled=False,
            self_second_pass_enabled=True,
            self_second_pass_min_top_score=0.9,
            iterative_enabled=False,
            candidate_pool_size=2,
        )
        with unittest.mock.patch.object(rag_mod, "_build_second_pass_queries", return_value=["beta"]):
            result = rag_mod.build_rag_package(
                user_text="alpha delta",
                knowledge_base=kb,
                top_k=1,
                config=cfg,
            )
        self.assertTrue(any("self_rag_second_pass=1" in t for t in result.trace))

    def test_build_rag_context_hybrid_merges_sources(self):
        kb = ["project planning checklist", "grounding breathing", "movie list"]

        class FakeEngine:
            def sync_docs(self, texts, persist=True):
                return None

            def retrieve_scored(self, query, top_k):
                return [
                    {"text": "movie list", "score": 1.0},
                    {"text": "project planning checklist", "score": 0.2},
                ]

        with unittest.mock.patch.object(rag_mod, "_get_engine", return_value=FakeEngine()):
            items = rag_mod.build_rag_context("project planning", kb, top_k=2, rag_mode="hybrid")
        self.assertGreaterEqual(len(items), 1)
        self.assertIn("project planning checklist", items)

    def test_corrective_filter_removes_low_score_noise(self):
        scored = [
            {"text": "noise", "score": 0.01},
            {"text": "project planning checklist", "score": 0.9},
        ]
        out = rag_mod._apply_corrective_filter_scored(
            user_text="project planning",
            scored_items=scored,
            top_k=2,
            min_score=0.08,
            enabled=True,
        )
        self.assertEqual(out[0]["text"], "project planning checklist")


if __name__ == "__main__":
    unittest.main()
