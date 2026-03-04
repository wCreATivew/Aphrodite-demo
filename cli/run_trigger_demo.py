from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from semantic_trigger.config import load_app_config
from semantic_trigger.engine import SemanticTriggerEngine
from semantic_trigger.registry import load_trigger_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantic Trigger demo")
    parser.add_argument(
        "--triggers",
        default=str(ROOT / "data" / "triggers" / "default_triggers.yaml"),
        help="Path to trigger registry file",
    )
    parser.add_argument(
        "--config",
        default=str(ROOT / "configs" / "app.example.yaml"),
        help="Path to app config",
    )
    parser.add_argument("--query", default="", help="User query")
    parser.add_argument("--debug", action="store_true", help="Verbose debug output")
    args = parser.parse_args()

    reg = load_trigger_registry(args.triggers)
    cfg = load_app_config(args.config if Path(args.config).exists() else "")
    engine = SemanticTriggerEngine.build_default(reg, cfg)

    enabled = reg.enabled_triggers()
    print(f"loaded_triggers={len(reg.triggers)} enabled={len(enabled)} top_k={cfg.top_k}")
    if not args.query:
        print("No query provided. Use --query to run inference.")
        return 0

    result = engine.infer(args.query)
    print(f"query={args.query}")
    print(
        f"decision={result.decision} selected={result.selected_trigger} "
        f"confidence={result.confidence:.4f}"
    )
    if result.extracted_slots:
        print("extracted_slots:", json.dumps(result.extracted_slots, ensure_ascii=False))
    if result.missing_slots:
        print("missing_slots:", ", ".join(result.missing_slots))
        print("clarification_suggestion:", "请补充以下信息: " + "、".join(result.missing_slots))

    if args.debug:
        rows = []
        for c in result.candidates:
            rows.append(
                {
                    "trigger_id": c.trigger_id,
                    "name": c.name,
                    "recall_score": round(c.recall_score, 4),
                    "rerank_score": round(c.rerank_score, 4),
                    "combined_score": round(c.combined_score, 4),
                    "reasons": c.reasons,
                }
            )
        print("top_k_candidates:")
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        print("debug_trace:")
        print(json.dumps(result.debug_trace, ensure_ascii=False, indent=2))
        print("decision_reasons:")
        print(json.dumps(result.reasons, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
