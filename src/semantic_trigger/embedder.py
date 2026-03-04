from __future__ import annotations

import math
import re
from hashlib import blake2b
from dataclasses import dataclass
from typing import Dict, Iterable, List, Protocol


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: List[str]) -> List[List[float]]: ...


_EN_RE = re.compile(r"[a-z0-9_]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def normalize_text(text: str) -> str:
    t = str(text or "").strip().lower()
    return re.sub(r"\s+", " ", t)


def tokenize(text: str) -> List[str]:
    t = normalize_text(text)
    if not t:
        return []
    en = _EN_RE.findall(t)
    zh_chars = _CJK_RE.findall(t)
    grams = char_ngrams(t, n_values=(2, 3))
    return en + zh_chars + grams


def char_ngrams(text: str, n_values: Iterable[int] = (2, 3)) -> List[str]:
    t = normalize_text(text)
    compact = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", t)
    out: List[str] = []
    for n in n_values:
        size = int(n)
        if size <= 0 or len(compact) < size:
            continue
        for i in range(0, len(compact) - size + 1):
            out.append(compact[i : i + size])
    return out


def token_counts(text: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for tok in tokenize(text):
        out[tok] = out.get(tok, 0) + 1
    return out


@dataclass
class SimpleHashEmbedder:
    dim: int = 256

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for text in texts:
            vec = [0.0] * int(self.dim)
            toks = tokenize(text)
            if not toks:
                out.append(vec)
                continue
            for tok in toks:
                idx = _stable_hash(tok) % int(self.dim)
                vec[idx] += 1.0
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            out.append(vec)
        return out


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n <= 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += float(a[i]) * float(b[i])
    return float(s)


def _stable_hash(text: str) -> int:
    h = blake2b(str(text).encode("utf-8"), digest_size=8)
    return int.from_bytes(h.digest(), byteorder="big", signed=False)
