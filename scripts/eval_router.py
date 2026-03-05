from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict
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


def _normalize_scope(raw: Any) -> str:
    if isinstance(raw, list):
        if not raw:
            return "MAIN"
        return str(raw[0] or "MAIN").upper()
    return str(raw or "MAIN").upper()


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
    confirm_ok = 0
    failures: List[Dict[str, Any]] = []
    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for r in rows:
        msg = str(r.get("input") or "")
        expected_action = _normalize_action(r.get("expected_action"))
        expected_scope = _normalize_scope(r.get("expected_scope"))
        expected_confirm = bool(r.get("needs_confirm", False))

        out = router.route(user_message=msg, user_profile={"target_profile": r.get("target_profile")}, recent_context=[])
        gated = fsm.apply(out, confirmed=False)

        pred_action = gated.action
        pred_scope = gated.scope
        pred_confirm = bool(gated.needs_confirm)

        action_hit += int(pred_action == expected_action)
        scope_hit += int(pred_scope == expected_scope)
        confirm_ok += int((not expected_confirm) or pred_confirm)
        confusion[expected_action][pred_action] += 1

        if not (pred_action == expected_action and pred_scope == expected_scope and ((not expected_confirm) or pred_confirm)):
            failures.append(
                {
                    "id": r.get("id"),
                    "input": msg,
                    "expected": {
                        "action": expected_action,
                        "scope": expected_scope,
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
    report = {
        "total": len(rows),
        "action_accuracy": round(action_hit / total, 4),
        "scope_accuracy": round(scope_hit / total, 4),
        "confirm_compliance": round(confirm_ok / total, 4),
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
