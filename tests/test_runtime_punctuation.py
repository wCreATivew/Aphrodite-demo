from __future__ import annotations

import unittest

from agentlib.runtime_engine import RuntimeEngine


class RuntimePunctuationTests(unittest.TestCase):
    def test_sanitize_normalizes_chinese_punctuation(self):
        text = "\u4f60\u597d , \u4e16\u754c ! \u6211\u4eec\u804a\u804a : \u8ba1\u5212 ."
        out = RuntimeEngine._sanitize_plain_text_reply(text)
        self.assertEqual(out, "\u4f60\u597d\uff0c\u4e16\u754c\uff01\u6211\u4eec\u804a\u804a\uff1a\u8ba1\u5212\u3002")

    def test_sanitize_keeps_url_colon(self):
        text = "\u53c2\u8003: https://example.com/docs"
        out = RuntimeEngine._sanitize_plain_text_reply(text)
        self.assertIn("https://example.com/docs", out)

    def test_prepare_tts_text_keeps_english_punctuation(self):
        out = RuntimeEngine._prepare_tts_text("Hello, world", enable_filler=False)
        self.assertEqual(out, "Hello, world.")

    def test_prepare_tts_text_normalizes_chinese_ellipsis(self):
        out = RuntimeEngine._prepare_tts_text("\u6211\u77e5\u9053...", enable_filler=False)
        self.assertEqual(out, "\u6211\u77e5\u9053\u2026\u2026")

    def test_short_paragraph_limits_sentences(self):
        text = "First sentence. Second sentence! Third sentence? Fourth sentence."
        out = RuntimeEngine._to_short_paragraph(text, max_sentences=3, max_chars=300)
        self.assertEqual(out, "First sentence.Second sentence!Third sentence?")

    def test_short_paragraph_limits_chars(self):
        text = "A long opening sentence with many words. Another sentence follows."
        out = RuntimeEngine._to_short_paragraph(text, max_sentences=3, max_chars=30)
        self.assertLessEqual(len(out), 31)
        self.assertTrue(out.endswith("."))


if __name__ == "__main__":
    unittest.main()
