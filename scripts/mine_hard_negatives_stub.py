from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stub miner for hard negatives from error rows")
    p.add_argument("--input", required=True, help="Input json/jsonl path")
    p.add_argument("--output", required=True, help="Output jsonl path")
    p.add_argument("--min-margin", type=float, default=0.0, help="Minimum margin to keep")
    return p.parse_args()


def load_rows(path: Path) -> List[Dict[str, Any]]:
    if path.suffix.lower() == ".json":
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            return [x for x in obj if isinstance(x, dict)]
        if isinstance(obj, dict):
            traces = obj.get("error_ledger") or obj.get("rows") or []
            if isinstance(traces, list):
                return [x for x in traces if isinstance(x, dict)]
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = str(raw or "").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def mine(rows: Iterable[Dict[str, Any]], min_margin: float = 0.0) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for r in rows:
        query = str(r.get("query") or "").strip()
        pred_decision = str(r.get("predicted_decision") or "")
        exp_decision = str(r.get("expected_decision") or "")
        pred_trigger = str(r.get("predicted_trigger") or "").strip()
        if not query or not pred_trigger:
            continue
        try:
            margin = float(r.get("margin") or 0.0)
        except Exception:
            margin = 0.0
        if margin < float(min_margin):
            continue
        if pred_decision == "trigger" and exp_decision in {"no_trigger", "ask_clarification"}:
            key = (query, pred_trigger)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "query": query,
                    "confusable_with": pred_trigger,
                    "source": "mine_hard_negatives_stub",
                    "margin": margin,
                }
            )
    return out


def save_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def main() -> int:
    args = parse_args()
    rows = load_rows(Path(args.input))
    hard = mine(rows, min_margin=float(args.min_margin))
    n = save_jsonl(Path(args.output), hard)
    print(f"input_rows={len(rows)} hard_negatives={n} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
