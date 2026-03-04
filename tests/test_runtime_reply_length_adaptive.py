from __future__ import annotations

import unittest

from agentlib.runtime_engine import RuntimeEngine


class RuntimeReplyLengthAdaptiveTests(unittest.TestCase):
    def test_parse_short_preference(self):
        pref = RuntimeEngine._parse_reply_length_preference("\u56de\u7b54\u7b80\u77ed\u4e00\u70b9")
        self.assertIsNotNone(pref)
        self.assertEqual(int(pref["max_sentences"]), 2)
        self.assertEqual(int(pref["max_chars"]), 120)
        self.assertFalse(bool(pref["persistent"]))

    def test_parse_persistent_long_preference(self):
        pref = RuntimeEngine._parse_reply_length_preference("\u4e4b\u540e\u90fd\u8be6\u7ec6\u4e00\u70b9")
        self.assertIsNotNone(pref)
        self.assertEqual(int(pref["max_sentences"]), 4)
        self.assertEqual(int(pref["max_chars"]), 260)
        self.assertTrue(bool(pref["persistent"]))

    def test_turn_preference_not_persistent(self):
        e = RuntimeEngine()
        e.force_one_sentence_output = False
        text = "\u7b2c\u4e00\u53e5\u3002\u7b2c\u4e8c\u53e5\u3002\u7b2c\u4e09\u53e5\u3002\u7b2c\u56db\u53e5\u3002"
        e._update_reply_length_preferences("\u8fd9\u6b21\u7b80\u77ed\u70b9")
        out_short = e._finalize_reply_text(text)
        self.assertEqual(out_short, "\u7b2c\u4e00\u53e5\u3002\u7b2c\u4e8c\u53e5\u3002")
        e._update_reply_length_preferences("\u7ee7\u7eed")
        out_default = e._finalize_reply_text(text)
        self.assertEqual(out_default, "\u7b2c\u4e00\u53e5\u3002\u7b2c\u4e8c\u53e5\u3002\u7b2c\u4e09\u53e5\u3002")

    def test_persistent_preference_and_reset(self):
        e = RuntimeEngine()
        e.force_one_sentence_output = False
        text = "\u7b2c\u4e00\u53e5\u3002\u7b2c\u4e8c\u53e5\u3002\u7b2c\u4e09\u53e5\u3002\u7b2c\u56db\u53e5\u3002\u7b2c\u4e94\u53e5\u3002"
        e._update_reply_length_preferences("\u4e4b\u540e\u90fd\u8be6\u7ec6\u4e00\u70b9")
        out1 = e._finalize_reply_text(text)
        self.assertEqual(out1, "\u7b2c\u4e00\u53e5\u3002\u7b2c\u4e8c\u53e5\u3002\u7b2c\u4e09\u53e5\u3002\u7b2c\u56db\u53e5\u3002")
        e._update_reply_length_preferences("\u7ee7\u7eed")
        out2 = e._finalize_reply_text(text)
        self.assertEqual(out2, "\u7b2c\u4e00\u53e5\u3002\u7b2c\u4e8c\u53e5\u3002\u7b2c\u4e09\u53e5\u3002\u7b2c\u56db\u53e5\u3002")
        e._update_reply_length_preferences("\u6062\u590d\u9ed8\u8ba4\u957f\u5ea6")
        e._update_reply_length_preferences("\u7ee7\u7eed")
        out3 = e._finalize_reply_text(text)
        self.assertEqual(out3, "\u7b2c\u4e00\u53e5\u3002\u7b2c\u4e8c\u53e5\u3002\u7b2c\u4e09\u53e5\u3002")


if __name__ == "__main__":
    unittest.main()
