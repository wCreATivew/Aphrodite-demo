from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List

_WORD_RE = re.compile(r"[a-z0-9_]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def normalize_text(text: Any) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"[\t\r\n]+", " ", raw)
    raw = re.sub(r"[^\w\u4e00-\u9fff]+", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def tokenize(text: Any) -> List[str]:
    norm = normalize_text(text)
    if not norm:
        return []
    latin = _WORD_RE.findall(norm)
    cjk_chars = _CJK_RE.findall(norm)
    cjk_bigrams = [cjk_chars[i] + cjk_chars[i + 1] for i in range(len(cjk_chars) - 1)]
    return latin + cjk_chars + cjk_bigrams


def token_counts(text: Any) -> Dict[str, int]:
    return dict(Counter(tokenize(text)))
