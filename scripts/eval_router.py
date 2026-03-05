from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agentlib.router.llm_router import LLMRouter, RouterStateMachine


def _normalize_action(raw: str) -> str:
    t = str(raw or "").strip().upper()
    mapping = {
        "AGENT_EXECUTE_LIGHT": "EXECUTE_LIGHT",
        "AGENT_EXECUTE_HEAVY": "EXECUTE_HEAVY",
        "CONFIRM_REQUIRED": "ASK_CLARIFY",
    }
    return mapping.get(t, t)


def _normalize_scope(raw: Any) -> List[str]:
    if isinstance(raw, list):
        if not raw:
            return ["MAIN"]
        return [str(x or "MAIN").upper() for x in raw]
    return [str(raw or "MAIN").upper()]


def _binary_f1(tp: int, fp: int, fn: int) -> float:
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _macro_f1(confusion: Dict[str, Dict[str, int]]) -> float:
    labels = sorted({*confusion.keys(), *{p for row in confusion.values() for p in row.keys()}})
    if not labels:
        return 0.0
    f1s: List[float] = []
    for label in labels:
        tp = confusion.get(label, {}).get(label, 0)
        fp = sum(confusion.get(other, {}).get(label, 0) for other in labels if other != label)
        fn = sum(confusion.get(label, {}).get(other, 0) for other in labels if other != label)
        f1s.append(_binary_f1(tp, fp, fn))
    return sum(f1s) / len(f1s)


def load_rows(pattern: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(pattern)):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                obj["__file"] = path
                rows.append(obj)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate LLM Router on jsonl datasets")
    parser.add_argument("--input", default="evals/*.jsonl")
    parser.add_argument("--report", default="report.json")
    args = parser.parse_args()

    rows = load_rows(args.input)
    if not rows:
        raise SystemExit(f"No eval rows found for pattern: {args.input}")

    router = LLMRouter()
    fsm = RouterStateMachine()

    action_hit = 0
    scope_hit = 0
    confirm_hit = 0
    confirm_tp = 0
    confirm_fp = 0
    confirm_fn = 0
    false_trigger = 0
    non_execute = 0
    failures: List[Dict[str, Any]] = []
    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    error_buckets: Counter[str] = Counter()

    for r in rows:
        msg = str(r.get("input") or "")
        expected_action = _normalize_action(r.get("expected_action"))
        expected_scopes = _normalize_scope(r.get("expected_scope"))
        expected_confirm = bool(r.get("needs_confirm", False) or str(r.get("expected_action", "")).upper() == "CONFIRM_REQUIRED")

        out = router.route(user_message=msg, user_profile={"target_profile": r.get("target_profile")}, recent_context=[])
        gated = fsm.apply(out, confirmed=False)

        pred_action = gated.action
        pred_scope = gated.scope
        pred_confirm = bool(gated.needs_confirm)

        action_hit += int(pred_action == expected_action)
        scope_ok = pred_scope in expected_scopes
        scope_hit += int(scope_ok)
        confirm_hit += int(pred_confirm == expected_confirm)
        confirm_tp += int(expected_confirm and pred_confirm)
        confirm_fp += int((not expected_confirm) and pred_confirm)
        confirm_fn += int(expected_confirm and (not pred_confirm))

        pred_is_execute = pred_action in {"EXECUTE_LIGHT", "EXECUTE_HEAVY"}
        expected_is_execute = expected_action in {"EXECUTE_LIGHT", "EXECUTE_HEAVY"}
        if not expected_is_execute:
            non_execute += 1
            false_trigger += int(pred_is_execute)

        confusion[expected_action][pred_action] += 1

        if not (pred_action == expected_action and scope_ok and pred_confirm == expected_confirm):
            if pred_action != expected_action:
                error_buckets["action_mismatch"] += 1
            if not scope_ok:
                error_buckets["scope_mismatch"] += 1
            if pred_confirm != expected_confirm:
                error_buckets["confirm_mismatch"] += 1
            failures.append(
                {
                    "id": r.get("id"),
                    "input": msg,
                    "expected": {
                        "action": expected_action,
                        "scope": expected_scopes,
                        "needs_confirm": expected_confirm,
                    },
                    "predicted": {
                        "action": pred_action,
                        "scope": pred_scope,
                        "needs_confirm": pred_confirm,
                        "reason": gated.reason,
                        "confidence": gated.confidence,
                    },
                }
            )

    total = max(1, len(rows))
    confirm_f1 = _binary_f1(confirm_tp, confirm_fp, confirm_fn)
    action_macro_f1 = _macro_f1(confusion)
    report = {
        "total": len(rows),
        "action_accuracy": round(action_hit / total, 4),
        "action_macro_f1": round(action_macro_f1, 4),
        "scope_accuracy": round(scope_hit / total, 4),
        "confirm_accuracy": round(confirm_hit / total, 4),
        "confirm_f1": round(confirm_f1, 4),
        "false_trigger_rate": round(false_trigger / max(1, non_execute), 4),
        "error_buckets": dict(error_buckets),
        "failures": failures,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
    }

    out_path = args.report
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
