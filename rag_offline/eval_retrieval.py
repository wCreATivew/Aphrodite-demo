from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from common import load_companion_rag_module, mrr_at_k, ndcg_at_k, read_jsonl, recall_at_k


def evaluate_dataset(
    rows: List[Dict[str, Any]],
    rag_mode: str,
    top_k: int,
    embed_model: str | None,
) -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    rag_mod = load_companion_rag_module(repo_root)
    cfg = rag_mod.load_rag_config()
    if embed_model:
        cfg.model_name = str(embed_model)

    sample_reports: List[Dict[str, Any]] = []
    recalls: List[float] = []
    mrrs: List[float] = []
    ndcgs: List[float] = []

    for row in rows:
        query = str(row.get("query", "")).strip()
        kb = [str(x).strip() for x in row.get("knowledge_base", []) if str(x).strip()]
        gold = [str(x).strip() for x in row.get("relevant", []) if str(x).strip()]
        if not query or not kb or not gold:
            continue

        result = rag_mod.build_rag_package(
            user_text=query,
            knowledge_base=kb,
            top_k=int(top_k),
            rag_mode=rag_mode,
            config=cfg,
        )
        pred = list(result.items)

        r = recall_at_k(pred, gold, k=top_k)
        m = mrr_at_k(pred, gold, k=top_k)
        n = ndcg_at_k(pred, gold, k=top_k)
        recalls.append(r)
        mrrs.append(m)
        ndcgs.append(n)

        sample_reports.append(
            {
                "query": query,
                "pred": pred,
                "gold": gold,
                "recall_at_k": r,
                "mrr_at_k": m,
                "ndcg_at_k": n,
                "mode_used": result.mode_used,
                "trace": result.trace,
                "retrieval_used": result.retrieval_used,
                "skip_reason": result.skip_reason,
            }
        )

    def _avg(xs: List[float]) -> float:
        return float(sum(xs) / max(1, len(xs)))

    return {
        "count": len(sample_reports),
        "rag_mode": rag_mode,
        "top_k": top_k,
        "recall_at_k": _avg(recalls),
        "mrr_at_k": _avg(mrrs),
        "ndcg_at_k": _avg(ndcgs),
        "samples": sample_reports,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="eval jsonl path")
    ap.add_argument("--rag-mode", default=os.getenv("RAG_MODE") or "hybrid")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--embed-model", default="", help="override RAG_EMBED_MODEL")
    ap.add_argument("--out", default="", help="optional report json path")
    args = ap.parse_args()

    rows = read_jsonl(args.dataset)
    report = evaluate_dataset(
        rows=rows,
        rag_mode=str(args.rag_mode).strip().lower(),
        top_k=max(1, int(args.top_k)),
        embed_model=(args.embed_model.strip() or None),
    )

    print(
        json.dumps(
            {
                "count": report["count"],
                "rag_mode": report["rag_mode"],
                "top_k": report["top_k"],
                "recall_at_k": round(float(report["recall_at_k"]), 4),
                "mrr_at_k": round(float(report["mrr_at_k"]), 4),
                "ndcg_at_k": round(float(report["ndcg_at_k"]), 4),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"wrote report -> {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
