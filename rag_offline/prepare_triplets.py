from __future__ import annotations

import argparse
import random
from typing import Any, Dict, List

from common import read_jsonl, write_jsonl


def build_triplets(rows: List[Dict[str, Any]], seed: int = 7) -> List[Dict[str, str]]:
    rng = random.Random(seed)
    out: List[Dict[str, str]] = []
    for row in rows:
        query = str(row.get("query", "")).strip()
        kb = [str(x).strip() for x in row.get("knowledge_base", []) if str(x).strip()]
        rel = [str(x).strip() for x in row.get("relevant", []) if str(x).strip()]
        if not query or not kb or not rel:
            continue

        rel_set = set(rel)
        neg = [x for x in kb if x not in rel_set]
        if not neg:
            continue

        for p in rel:
            n = rng.choice(neg)
            out.append({"query": query, "positive": p, "negative": n})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="input retrieval dataset jsonl")
    ap.add_argument("--output", required=True, help="output triplets jsonl")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rows = read_jsonl(args.input)
    triplets = build_triplets(rows, seed=args.seed)
    write_jsonl(args.output, triplets)
    print(f"wrote {len(triplets)} triplets -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
