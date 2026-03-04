from __future__ import annotations

import json
import unittest
from pathlib import Path

import run_kernel_v16_demo


class DemoNoInfiniteFallbackTests(unittest.TestCase):
    def test_kernel_v16_demo_reaches_terminal_state(self):
        rc = run_kernel_v16_demo.main()
        self.assertEqual(rc, 0)
        ckpt = Path("outputs/agent_kernel_v16_checkpoint.json")
        self.assertTrue(ckpt.exists())
        obj = json.loads(ckpt.read_text(encoding="utf-8"))
        status = str(obj.get("status") or "")
        self.assertIn(status, {"done", "failed", "waiting_user"})


if __name__ == "__main__":
    unittest.main()

