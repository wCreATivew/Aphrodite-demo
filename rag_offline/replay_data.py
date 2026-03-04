from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def enrich_sessions(
    sessions: List[Dict[str, Any]],
    triplets: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    triplets = triplets or []
    t_idx = 0
    for i, s in enumerate(sessions):
        row = dict(s)
        row["_idx"] = i + 1
        row["_triplet"] = None
        if bool(row.get("triplet_generated")) and t_idx < len(triplets):
            row["_triplet"] = triplets[t_idx]
            t_idx += 1
        out.append(row)
    return out


def filter_sessions(
    sessions: List[Dict[str, Any]],
    *,
    keyword: str = "",
    signal: Optional[int] = None,
    retrieval_used: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    kw = str(keyword or "").strip().lower()
    out: List[Dict[str, Any]] = []
    for row in sessions:
        if signal is not None and int(row.get("feedback_signal", 0)) != int(signal):
            continue
        if retrieval_used is not None and bool(row.get("retrieval_used", False)) != bool(retrieval_used):
            continue
        if kw:
            text = " ".join(
                [
                    str(row.get("query", "")),
                    " ".join(str(x) for x in row.get("retrieved", []) if str(x).strip()),
                    str(row.get("feedback", "")),
                ]
            ).lower()
            if kw not in text:
                continue
        out.append(row)
    return out


def summarize_sessions(sessions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(sessions)
    total = len(rows)
    feedback_pos = sum(1 for x in rows if int(x.get("feedback_signal", 0)) > 0)
    feedback_neg = sum(1 for x in rows if int(x.get("feedback_signal", 0)) < 0)
    feedback_neu = total - feedback_pos - feedback_neg
    retrieval_used = sum(1 for x in rows if bool(x.get("retrieval_used", False)))
    triplet_generated = sum(1 for x in rows if bool(x.get("triplet_generated", False)))
    return {
        "total": total,
        "feedback_pos": feedback_pos,
        "feedback_neg": feedback_neg,
        "feedback_neu": feedback_neu,
        "retrieval_used": retrieval_used,
        "triplet_generated": triplet_generated,
    }
