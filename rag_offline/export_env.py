from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _safe_get(d: Dict[str, Any], key: str, default: Any) -> Any:
    v = d.get(key, default)
    return default if v is None else v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune-report", required=True, help="output of tune_rag_params.py")
    ap.add_argument("--output", default="rag_offline/best_rag.env")
    ap.add_argument("--embed-model", default="", help="optional model path to export")
    args = ap.parse_args()

    with open(args.tune_report, "r", encoding="utf-8") as f:
        report = json.load(f)

    best = report.get("best") or {}
    params = best.get("params") or {}
    rag_mode = str(report.get("rag_mode") or "hybrid")

    lines = [
        f"RAG_MODE={rag_mode}",
        f"RAG_HYBRID_EMBED_WEIGHT={_safe_get(params, 'hybrid_embed_weight', 0.7)}",
        f"RAG_HYBRID_KEYWORD_WEIGHT={_safe_get(params, 'hybrid_keyword_weight', 0.3)}",
        f"RAG_CORRECTIVE_MIN_SCORE={_safe_get(params, 'corrective_min_score', 0.08)}",
        f"RAG_SELF_SECOND_PASS_MIN_TOP_SCORE={_safe_get(params, 'self_second_pass_min_top_score', 0.26)}",
        f"RAG_DIVERSITY_MIN_JACCARD_GAP={_safe_get(params, 'diversity_min_jaccard_gap', 0.08)}",
    ]
    if args.embed_model.strip():
        lines.append(f"RAG_EMBED_MODEL={args.embed_model.strip()}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    print(f"wrote env snippet -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
