from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from engine_adapter import build_engine_adapter as _build_engine_adapter
except Exception:
    try:
        from cli.engine_adapter import build_engine_adapter as _build_engine_adapter
    except Exception:
        _build_engine_adapter = None

from semantic_trigger.error_analysis import (
    collect_false_negatives,
    collect_false_positives,
    summarize_by_trigger,
    top_confusion_pairs,
)
from semantic_trigger.metrics import (
    ask_clarification_metrics,
    decision_classification_metrics,
    no_trigger_metrics,
    to_eval_rows,
    trigger_match_stats,
)


class _StubAdapter:
    def infer(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        q = str(query or "").lower()
        if any(x in q for x in ["remind", "提醒", "alarm", "闹钟"]):
            return {"decision": "trigger", "selected_trigger": "set_reminder"}
        if any(x in q for x in ["message", "发消息", "text"]):
            return {"decision": "trigger", "selected_trigger": "send_message"}
        if any(x in q for x in ["weather", "天气"]):
            return {"decision": "trigger", "selected_trigger": "weather_query"}
        if any(x in q for x in ["maybe", "不确定", "unclear"]):
            return {"decision": "ask_clarification", "selected_trigger": ""}
        return {"decision": "no_trigger", "selected_trigger": ""}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semantic trigger evaluation with diagnostics")
    parser.add_argument("--dataset", required=True, help="Path to jsonl dataset")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K candidates")
    parser.add_argument("--triggers-path", default="", help="Path to trigger definitions")
    parser.add_argument("--save-report", default="", help="Path to save full report JSON")
    parser.add_argument("--save-errors", default="", help="Path to save error cases JSON/JSONL")
    parser.add_argument("--save-trace", default="", help="Path to save trace JSONL")
    parser.add_argument("--force-stub", action="store_true", help="Force stub adapter")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ds = Path(args.dataset)
    if not ds.exists():
        print(f"ERROR: dataset not found: {ds}")
        return 2

    adapter = _resolve_adapter(force_stub=bool(args.force_stub), triggers_path=str(args.triggers_path or ""))
    rows = _run_eval(adapter=adapter, dataset_path=ds, top_k=max(1, int(args.top_k)))
    report = _build_report(rows)

    _print_summary(report)
    if args.save_report:
        _save_json(Path(args.save_report), report)
        print(f"saved_report={args.save_report}")
    if args.save_trace:
        _save_jsonl(Path(args.save_trace), rows)
        print(f"saved_trace={args.save_trace}")
    if args.save_errors:
        _save_errors(Path(args.save_errors), report["errors"])
        print(f"saved_errors={args.save_errors}")
    return 0


def _resolve_adapter(*, force_stub: bool, triggers_path: str) -> Any:
    if force_stub:
        return _StubAdapter()
    if _build_engine_adapter is None:
        return _StubAdapter()
    try:
        return _build_engine_adapter(triggers_path=triggers_path, prefer_real=True)
    except Exception:
        return _StubAdapter()


def _run_eval(*, adapter: Any, dataset_path: Path, top_k: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8-sig") as f:
        for idx, raw in enumerate(f, start=1):
            line = str(raw or "").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            query = str(obj.get("query") or "").strip()
            if not query:
                continue
            expected_decision = str(obj.get("expected_decision") or "no_trigger")
            expected_trigger = str(obj.get("expected_trigger") or "")
            pred = adapter.infer(query, top_k=top_k)
            predicted_decision = str(_pick(pred, "decision", "no_trigger"))
            predicted_trigger = str(_pick(pred, "selected_trigger", ""))
            out.append(
                {
                    "row_id": idx,
                    "query": query,
                    "expected_decision": expected_decision,
                    "expected_trigger": expected_trigger,
                    "predicted_decision": predicted_decision,
                    "predicted_trigger": predicted_trigger,
                    "difficulty": str(obj.get("difficulty") or "unknown"),
                }
            )
    return out


def _build_report(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    eval_rows = to_eval_rows(rows)
    decision_metrics = decision_classification_metrics(eval_rows)
    trigger_metrics = trigger_match_stats(eval_rows)
    no_trig = no_trigger_metrics(eval_rows)
    ask_clar = ask_clarification_metrics(eval_rows)

    false_pos = collect_false_positives(rows, limit=30)
    false_neg = collect_false_negatives(rows, limit=30)
    confusions = top_confusion_pairs(rows, top_n=20)
    by_trigger = summarize_by_trigger(rows)

    return {
        "total": len(rows),
        "decision_metrics": decision_metrics,
        "trigger_metrics": trigger_metrics,
        "no_trigger_metrics": no_trig,
        "ask_clarification_metrics": ask_clar,
        "false_positive_top_cases": false_pos[:10],
        "false_negative_top_cases": false_neg[:10],
        "confusion_pairs": confusions,
        "summary_by_trigger": by_trigger,
        "errors": {
            "false_positives": false_pos,
            "false_negatives": false_neg,
            "confusion_pairs": confusions,
        },
    }


def _print_summary(report: Dict[str, Any]) -> None:
    print(f"total={report['total']}")
    print(f"decision_accuracy={report['decision_metrics']['decision_accuracy']}")
    print(f"trigger_match_rate={report['trigger_metrics']['trigger_match_rate']}")
    print(
        "no_trigger_f1="
        + str(report["no_trigger_metrics"]["f1"])
        + " ask_clarification_f1="
        + str(report["ask_clarification_metrics"]["f1"])
    )
    print("confusion_pairs_top3=" + json.dumps(report["confusion_pairs"][:3], ensure_ascii=False))
    print("false_positive_top3=" + json.dumps(report["false_positive_top_cases"][:3], ensure_ascii=False))
    print("false_negative_top3=" + json.dumps(report["false_negative_top_cases"][:3], ensure_ascii=False))


def _save_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")


def _save_errors(path: Path, errors: Dict[str, Any]) -> None:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        all_rows: List[Dict[str, Any]] = []
        for key, values in errors.items():
            if isinstance(values, list):
                for item in values:
                    row = dict(item)
                    row["error_group"] = key
                    all_rows.append(row)
        _save_jsonl(path, all_rows)
        return
    _save_json(path, errors)


def _pick(obj: Any, key: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


if __name__ == "__main__":
    raise SystemExit(main())
