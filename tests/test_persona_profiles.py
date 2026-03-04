from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


if "agentlib" not in sys.modules:
    pkg = types.ModuleType("agentlib")
    pkg.__path__ = [str(ROOT / "agentlib")]
    sys.modules["agentlib"] = pkg

profiles_mod = _load_module("agentlib.persona_profiles", ROOT / "agentlib" / "persona_profiles.py")


class PersonaProfilesTests(unittest.TestCase):
    def test_codex52_profile_available(self):
        names = profiles_mod.list_persona_profiles()
        self.assertIn("codex5.2", names)

    def test_codex52_alias_supported(self):
        p = profiles_mod.get_persona_profile("codex52")
        self.assertEqual(p.name, "codex5.2")


if __name__ == "__main__":
    unittest.main()
