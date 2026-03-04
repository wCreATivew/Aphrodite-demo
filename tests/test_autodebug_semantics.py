from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from agentlib.autodebug import auto_debug_python_file


class AutoDebugSemanticsTests(unittest.TestCase):
    @patch("agentlib.autodebug._request_patch_from_model")
    def test_target_error_does_not_noop_success_in_zero_round(self, mock_patch):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "demo.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("value = 1\n")
            mock_patch.side_effect = lambda source, **kwargs: source
            result = auto_debug_python_file(
                file_path=path,
                max_rounds=1,
                error_context=f"{path}:1 - error: target static issue",
            )
            self.assertFalse(bool(result.ok))
            self.assertNotIn("success in 0 round(s)", str(result.message))
            self.assertEqual(str(result.classification), "failed")
            self.assertEqual(int(result.applied_rounds), 0)
            self.assertFalse(bool(result.changed))

    @patch("agentlib.autodebug._request_patch_from_model")
    def test_unrelated_error_context_is_skipped(self, mock_patch):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "demo.py")
            other = os.path.join(td, "other.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("value = 1\n")
            mock_patch.return_value = "value = 2\n"
            result = auto_debug_python_file(
                file_path=path,
                max_rounds=1,
                error_context=f"{other}:5 - error: unrelated issue",
            )
            self.assertFalse(bool(result.ok))
            self.assertEqual(str(result.classification), "skipped")
            self.assertEqual(str(result.skip_reason), "error not for target")
            self.assertFalse(bool(result.changed))
            self.assertEqual(int(mock_patch.call_count), 0)

    @patch("agentlib.autodebug._request_patch_from_model")
    def test_success_requires_real_change(self, mock_patch):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "demo.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("value = 1\n")
            mock_patch.return_value = "value = 2\n"
            result = auto_debug_python_file(
                file_path=path,
                max_rounds=1,
                error_context=f"{path}:1 - error: target static issue",
            )
            self.assertTrue(bool(result.ok))
            self.assertEqual(str(result.classification), "patched")
            self.assertTrue(bool(result.changed))
            self.assertGreaterEqual(int(result.applied_rounds), 1)
            with open(path, "r", encoding="utf-8") as f:
                self.assertIn("value = 2", f.read())


if __name__ == "__main__":
    unittest.main()
