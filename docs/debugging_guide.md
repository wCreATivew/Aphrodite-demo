# Debugging Guide

## 1) Single Query Debug
Run:

```bash
python -m cli.run_trigger_demo --query "明天下午三点提醒我开会" --debug
```

Inspect:
- `top_k_candidates`: recall/rerank/combined score
- `debug_trace.top1/top2/margin`
- `constraint_passed/failed`
- `slot_reasons`, `missing_slots`, `extracted_slots`
- `decision_reasons`

## 2) Batch Evaluation
Run:

```bash
python -m cli.eval_trigger_engine \
  --dataset data/eval/eval_dataset.jsonl \
  --save-report outputs/report.json \
  --save-trace outputs/trace.jsonl
```

Artifacts:
- `outputs/report.json`: overall metrics, trigger-level metrics, confusion pairs, FP/FN cases.
- `outputs/trace.jsonl`: per-sample inference traces for replay and hard-negative mining.

## 3) Common Failure Modes
- Low recall: enrich trigger aliases/positive examples.
- False trigger: add hard negatives and tighten per-trigger threshold.
- Over-no-trigger: reduce threshold or increase lexical/alias signal.
- Slot not extracted: add slot-specific extraction hints/patterns.

## 4) Fast Tuning Checklist
1. Check `combined_score` distribution for TP/FP/FN.
2. Tune per-trigger thresholds first, global thresholds second.
3. Add hard negatives for top confusion pairs.
4. Keep fallback trigger constrained (`requires_any_keyword`).

## 5) Runtime Integration
`agentlib/runtime_engine.py` now calls semantic trigger before the LLM path.

Useful env flags:
- `SEMANTIC_TRIGGER_ENABLED=1`
- `SEMANTIC_TRIGGER_REGISTRY=data/triggers/default_triggers.yaml`
- `SEMANTIC_TRIGGER_CONFIG=configs/app.example.yaml`
- `SEMANTIC_TRIGGER_TOP_K=20`
- `DEBUG_SEMANTIC_MIN_CONFIDENCE=0.70` (debug-mode trigger threshold)
- `SEMANTIC_DEBUG_AUTOFIX_ENABLED=1`
- `SEMANTIC_DEBUG_AUTOFIX_ROUNDS=2`
- `AUTODEBUG_VERIFY_COMMAND="<your test command>"`

Behavior:
- `code_debug` trigger: enters debug mode reply path directly.
- If `code_debug` query contains a `.py` target path, runtime executes `selfcheck/autodebug` workflow.
- `ask_clarification`: returns missing-slot prompt for actionable intents.
- If semantic layer abstains, runtime falls back to normal LLM response flow.
