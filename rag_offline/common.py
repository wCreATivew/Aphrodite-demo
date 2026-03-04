from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def recall_at_k(pred: Sequence[str], gold: Sequence[str], k: int) -> float:
    p = list(pred[: max(0, k)])
    g = set(str(x) for x in gold)
    if not g:
        return 0.0
    hit = sum(1 for x in p if x in g)
    return float(hit) / float(len(g))


def mrr_at_k(pred: Sequence[str], gold: Sequence[str], k: int) -> float:
    g = set(str(x) for x in gold)
    for i, x in enumerate(pred[: max(0, k)], start=1):
        if x in g:
            return 1.0 / float(i)
    return 0.0


def ndcg_at_k(pred: Sequence[str], gold: Sequence[str], k: int) -> float:
    g = set(str(x) for x in gold)
    if not g:
        return 0.0
    dcg = 0.0
    for i, x in enumerate(pred[: max(0, k)], start=1):
        rel = 1.0 if x in g else 0.0
        if rel > 0:
            dcg += rel / _log2(i + 1)
    ideal_hits = min(len(g), max(0, k))
    idcg = sum(1.0 / _log2(i + 1) for i in range(1, ideal_hits + 1))
    if idcg <= 0:
        return 0.0
    return dcg / idcg


def _log2(x: float) -> float:
    import math

    return math.log(x, 2)


def load_companion_rag_module(repo_root: Path):
    """
    Load agentlib/companion_rag.py directly without importing agentlib/__init__.py.
    This avoids unrelated heavy dependency imports during offline scripts.
    """
    mod_path = repo_root / "agentlib" / "companion_rag.py"
    spec = importlib.util.spec_from_file_location("companion_rag_offline", str(mod_path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod
