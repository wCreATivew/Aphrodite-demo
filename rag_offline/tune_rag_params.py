from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any, Dict, List

from common import load_companion_rag_module, mrr_at_k, ndcg_at_k, read_jsonl, recall_at_k


def evaluate_with_config(rows: List[Dict[str, Any]], cfg, rag_mod, top_k: int, rag_mode: str) -> Dict[str, float]:
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
            top_k=top_k,
            rag_mode=rag_mode,
            config=cfg,
        )
        pred = list(result.items)
        recalls.append(recall_at_k(pred, gold, k=top_k))
        mrrs.append(mrr_at_k(pred, gold, k=top_k))
        ndcgs.append(ndcg_at_k(pred, gold, k=top_k))

    def _avg(xs: List[float]) -> float:
        return float(sum(xs) / max(1, len(xs)))

    return {
        "recall_at_k": _avg(recalls),
        "mrr_at_k": _avg(mrrs),
        "ndcg_at_k": _avg(ndcgs),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="eval jsonl")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--rag-mode", default="hybrid", choices=["hybrid", "embedding", "keyword"])
    ap.add_argument("--out", default="rag_offline/tune_report.json")
    args = ap.parse_args()

    rows = read_jsonl(args.dataset)
    repo_root = Path(__file__).resolve().parents[1]
    rag_mod = load_companion_rag_module(repo_root)
    base_cfg = rag_mod.load_rag_config()

    embed_weights = [0.6, 0.7, 0.8]
    min_scores = [0.05, 0.08, 0.12]
    second_pass_scores = [0.2, 0.26, 0.32]
    diversity_gaps = [0.05, 0.08, 0.12]

    trials: List[Dict[str, Any]] = []
    best: Dict[str, Any] | None = None

    for ew, ms, sps, dg in itertools.product(embed_weights, min_scores, second_pass_scores, diversity_gaps):
        cfg = rag_mod.RagConfig(**vars(base_cfg))
        cfg.hybrid_embed_weight = float(ew)
        cfg.hybrid_keyword_weight = max(0.0, 1.0 - float(ew))
        cfg.corrective_min_score = float(ms)
        cfg.self_second_pass_min_top_score = float(sps)
        cfg.diversity_min_jaccard_gap = float(dg)
        cfg.debug_enabled = False

        metrics = evaluate_with_config(
            rows=rows,
            cfg=cfg,
            rag_mod=rag_mod,
            top_k=max(1, int(args.top_k)),
            rag_mode=args.rag_mode,
        )
        score = 0.5 * metrics["recall_at_k"] + 0.3 * metrics["mrr_at_k"] + 0.2 * metrics["ndcg_at_k"]
        trial = {
            "params": {
                "hybrid_embed_weight": cfg.hybrid_embed_weight,
                "hybrid_keyword_weight": cfg.hybrid_keyword_weight,
                "corrective_min_score": cfg.corrective_min_score,
                "self_second_pass_min_top_score": cfg.self_second_pass_min_top_score,
                "diversity_min_jaccard_gap": cfg.diversity_min_jaccard_gap,
            },
            "metrics": metrics,
            "score": score,
        }
        trials.append(trial)
        if best is None or float(score) > float(best["score"]):
            best = trial

    report = {
        "dataset": args.dataset,
        "top_k": int(args.top_k),
        "rag_mode": args.rag_mode,
        "trials": trials,
        "best": best,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if best:
        print("best_score=", round(float(best["score"]), 4))
        print(json.dumps(best, ensure_ascii=False, indent=2))
    print(f"wrote tune report -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
