from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from semantic_trigger.config import load_app_config
from semantic_trigger.engine import SemanticTriggerEngine
from semantic_trigger.error_ledger import (
    append_jsonl_unique,
    build_hard_negatives_from_ledger,
    build_ledger_entry,
    summarize_ledger,
)
from semantic_trigger.metrics import (
    EvalRow,
    compute_decision_level_metrics,
    compute_difficulty_metrics,
    compute_error_type_breakdown,
    compute_overall_metrics,
    compute_trigger_level_metrics,
    confusion_pairs,
    false_cases,
)
from semantic_trigger.registry import load_trigger_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch evaluate semantic trigger engine")
    parser.add_argument("--dataset", required=True, help="Path to jsonl dataset")
    parser.add_argument(
        "--triggers",
        default=str(ROOT / "data" / "triggers" / "default_triggers.yaml"),
        help="Path to trigger registry",
    )
    parser.add_argument(
        "--config",
        default=str(ROOT / "configs" / "app.example.yaml"),
        help="Path to app config",
    )
    parser.add_argument("--save-report", default="", help="Path to save report json")
    parser.add_argument("--save-trace", default="", help="Path to save prediction trace jsonl")
    parser.add_argument("--save-error-ledger", default="", help="Path to save error ledger jsonl")
    parser.add_argument("--save-ledger", default="", help="Compatibility alias of --save-error-ledger")
    parser.add_argument("--save-hard-negatives", default="", help="Path to append mined hard negatives jsonl")
    parser.add_argument("--hard-negatives", default="", help="Optional hard negatives jsonl used as extra eval split")
    parser.add_argument("--config-version", default="", help="Override config version")
    parser.add_argument("--policy-version", default="", help="Override policy version")
    parser.add_argument("--dataset-version", default="", help="Override dataset version")
    args = parser.parse_args()

    reg = load_trigger_registry(args.triggers)
    cfg = load_app_config(args.config if Path(args.config).exists() else "")
    engine = SemanticTriggerEngine.build_default(reg, cfg)
    if getattr(engine, "logger", None) is not None:
        engine.logger.setLevel(logging.WARNING)

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")

    run_ts = datetime.now(timezone.utc).isoformat()
    config_version = str(args.config_version or Path(args.config).name or "default")
    policy_version = str(args.policy_version or "default")
    dataset_version = str(args.dataset_version or dataset_path.stem or "unknown")

    dataset_rows = _load_dataset_rows(dataset_path, split="main")
    if args.hard_negatives:
        hn_path = Path(args.hard_negatives)
        if not hn_path.exists():
            raise FileNotFoundError(f"hard negatives file not found: {hn_path}")
        dataset_rows.extend(_load_dataset_rows(hn_path, split="hard_negative", default_decision="no_trigger"))

    rows: List[EvalRow] = []
    traces: List[Dict] = []
    ledger_rows: List[Dict] = []
    for obj in dataset_rows:
        query = str(obj.get("query") or "")
        expected_decision = str(obj.get("expected_decision") or "no_trigger")
        expected_trigger = str(obj.get("expected_trigger") or "")
        difficulty = str(obj.get("difficulty") or "unknown")
        split = str(obj.get("_split") or "main")

        pred = engine.infer(query)
        debug = dict(pred.debug_trace or {})
        ledger = build_ledger_entry(
            query=query,
            predicted_decision=str(pred.decision or "no_trigger"),
            predicted_trigger=str(pred.selected_trigger or ""),
            expected_decision=expected_decision,
            expected_trigger=expected_trigger,
            top_k_candidates=[str(x) for x in (debug.get("top_k_candidates") or [])],
            recall_scores=dict(debug.get("recall_scores") or {}),
            rerank_scores=dict(debug.get("rerank_scores") or {}),
            margin=float(debug.get("margin", 0.0) or 0.0),
            extracted_slots=dict(pred.extracted_slots or {}),
            missing_slots=list(pred.missing_slots or []),
            clarification_question=pred.clarification_question,
            reasons=list(pred.reasons or []),
            config_version=config_version,
            policy_version=policy_version,
            dataset_version=dataset_version,
            timestamp=run_ts,
        )
        ledger["split"] = split
        ledger["difficulty"] = difficulty
        ledger_rows.append(ledger)

        rows.append(
            EvalRow(
                query=query,
                expected_decision=expected_decision,
                expected_trigger=expected_trigger,
                predicted_decision=str(pred.decision or "no_trigger"),
                predicted_trigger=str(pred.selected_trigger or ""),
                difficulty=difficulty,
                split=split,
                error_type=str(ledger.get("error_type") or ""),
            )
        )
        traces.append(
            {
                "query": query,
                "predicted_decision": pred.decision,
                "predicted_trigger": pred.selected_trigger,
                "expected_decision": expected_decision,
                "expected_trigger": expected_trigger,
                "top_k_candidates": ledger.get("top_k_candidates", []),
                "recall_scores": ledger.get("recall_scores", {}),
                "rerank_scores": ledger.get("rerank_scores", {}),
                "margin": ledger.get("margin", 0.0),
                "extracted_slots": pred.extracted_slots,
                "missing_slots": pred.missing_slots,
                "clarification_question": pred.clarification_question,
                "reasons": pred.reasons,
                "config_version": config_version,
                "policy_version": policy_version,
                "dataset_version": dataset_version,
                "timestamp": run_ts,
            }
        )

    overall = compute_overall_metrics(rows)
    decision_level = compute_decision_level_metrics(rows)
    difficulty_level = compute_difficulty_metrics(rows)
    trigger_level = compute_trigger_level_metrics(rows)
    confusion = confusion_pairs(rows, top_n=20)
    false_summary = false_cases(rows, limit=40)
    error_breakdown = compute_error_type_breakdown(rows)
    ledger_summary = summarize_ledger(ledger_rows)

    hard_negative_rows = [r for r in rows if r.split == "hard_negative"]
    hard_negative = compute_overall_metrics(hard_negative_rows) if hard_negative_rows else {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "decision_accuracy": 0.0,
        "tp": 0.0,
        "fp": 0.0,
        "fn": 0.0,
        "total": 0.0,
    }

    report = {
        "versions": {
            "config_version": config_version,
            "policy_version": policy_version,
            "dataset_version": dataset_version,
            "timestamp": run_ts,
        },
        "overall": overall,
        "decision_level": decision_level,
        "difficulty_level": difficulty_level,
        "error_type_breakdown": error_breakdown,
        "hard_negative": hard_negative,
        "ledger_summary": ledger_summary,
        "trigger_level": trigger_level,
        "confusion_pairs": confusion,
        "false_positive_top_cases": false_summary["false_positive"],
        "false_negative_top_cases": false_summary["false_negative"],
        "dataset_size": len(rows),
    }

    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"dataset_size={len(rows)} confusion_pairs={len(confusion)}")
    print("error_count=" + str(ledger_summary.get("error_count", 0)))

    if args.save_report:
        report_path = Path(args.save_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved_report={report_path}")

    if args.save_trace:
        trace_path = Path(args.save_trace)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("w", encoding="utf-8") as fw:
            for row in traces:
                fw.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"saved_trace={trace_path}")

    if args.save_error_ledger or args.save_ledger:
        ledger_path = Path(args.save_error_ledger or args.save_ledger)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("w", encoding="utf-8") as fw:
            for row in ledger_rows:
                fw.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"saved_error_ledger={ledger_path}")
    if args.save_hard_negatives:
        mined = build_hard_negatives_from_ledger(ledger_rows, min_margin=0.0)
        merged_total = append_jsonl_unique(args.save_hard_negatives, mined, dedupe_key="query")
        print(f"saved_hard_negatives={args.save_hard_negatives} merged_total={merged_total}")

    return 0


def _load_dataset_rows(path: Path, *, split: str, default_decision: str = "") -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for raw in f:
            line = str(raw or "").strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            row = dict(obj)
            row.setdefault("expected_decision", default_decision or "no_trigger")
            row.setdefault("expected_trigger", "")
            row["_split"] = split
            rows.append(row)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())

