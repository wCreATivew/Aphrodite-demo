from __future__ import annotations

import importlib.util
import inspect
import re
import subprocess
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_rag_path_agentlib"


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


pkg = types.ModuleType(PACKAGE_NAME)
pkg.__path__ = [str(ROOT / "agentlib")]
sys.modules[PACKAGE_NAME] = pkg
_load_module(f"{PACKAGE_NAME}.learned_lists", ROOT / "agentlib" / "learned_lists.py")
memory_store = _load_module(f"{PACKAGE_NAME}.memory_store", ROOT / "agentlib" / "memory_store.py")


class RuntimeRagArtifactPathTests(unittest.TestCase):
    def test_default_memory_store_artifacts_resolve_under_var(self):
        defaults = inspect.signature(memory_store.MemoryStore.__init__).parameters
        expected = {
            "db_path": ROOT / "var" / "db" / "memory.sqlite",
            "index_path": ROOT / "var" / "indexes" / "memory.faiss",
            "ids_path": ROOT / "var" / "indexes" / "memory_ids.npy",
        }

        for parameter, target in expected.items():
            actual = Path(defaults[parameter].default).resolve()
            self.assertEqual(actual, target.resolve())
            self.assertNotEqual(actual.parent, ROOT.resolve())

    def test_generated_artifact_root_constant_is_repository_var(self):
        self.assertEqual(memory_store.GENERATED_ARTIFACT_ROOT.resolve(), (ROOT / "var").resolve())

    def test_generated_artifact_layout_is_git_ignored(self):
        paths = [
            "var/db/memory.sqlite",
            "var/indexes/memory.faiss",
            "var/indexes/memory_ids.npy",
            "var/models/embedding/rag_embed_model/config.json",
            "var/reports/rag/tune_report.json",
            "var/data/rag/conversation_sessions.jsonl",
        ]
        for path in paths:
            result = subprocess.run(
                ["git", "check-ignore", "--quiet", "--", path],
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=f"Expected git to ignore {path}")

    def test_example_environment_has_no_populated_api_keys(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        for key, value in re.findall(r"^([A-Z0-9_]*API_KEY)=(.*)$", env_example, re.MULTILINE):
            cleaned = value.strip().lower()
            is_placeholder = not cleaned or "your" in cleaned or "placeholder" in cleaned or cleaned.startswith("<")
            self.assertTrue(is_placeholder, msg=f"{key} is populated")


if __name__ == "__main__":
    unittest.main()
