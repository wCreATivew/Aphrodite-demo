# Debugging Guide

This guide focuses on diagnosing trigger misclassification with a contract-first workflow.

## 1) Inspect Top-K Candidates

Run demo in debug mode:

```bash
py cli/run_trigger_demo.py --query "给他发消息" --debug
```

Look at:
- `decision`: final decision (`trigger/no_trigger/ask_clarification`)
- `selected_trigger`: chosen trigger id or `null`
- `top_k_candidates`: each candidate's `recall_score/rerank_score/final_score`
- `missing_slots`: required slot gaps
- `reasons` + `debug`: threshold and margin evidence

## 2) Diagnose False Trigger (误触发)

Symptoms:
- expected `no_trigger`, predicted `trigger`

Checklist:
- query overlaps too strongly with trigger aliases
- negatives are too weak in trigger definition
- decision threshold too low for that trigger

Actions:
- add hard negatives into `negative_examples`
- add out-of-domain no-trigger rows into `data/eval/eval_dataset.jsonl`
- include confusion cases (e.g., architecture/tutorial wording)

## 3) Diagnose Missed Trigger (漏触发)

Symptoms:
- expected `trigger`, predicted `no_trigger` or wrong trigger

Checklist:
- positive examples do not cover real phrasing
- aliases miss common shorthand/mixed language
- slot extraction misses required fields due to phrasing

Actions:
- enrich `aliases` and `positive_examples`
- add mixed-language and short-command samples
- add ask_clarification samples for partial intent

## 4) Diagnose Over-Clarification

Symptoms:
- expected `trigger`, predicted `ask_clarification`

Checklist:
- required slot design too strict
- query has implicit slot but extraction rule misses it

Actions:
- verify whether slot should be optional instead of required
- improve extraction hints in slot spec
- add successful trigger examples with similar wording

## 5) Use Hard Negatives Effectively

Add rows that are lexically similar but semantically out-of-scope:
- "message queue tutorial" vs `send_message`
- "alarm clock circuit design" vs `set_alarm`
- "translation benchmark datasets" vs `translate_text`

These should be labeled:
- `expected_decision = no_trigger`
- optional `notes = hard negative`
- `difficulty = hard`

## 6) Minimal Debug Loop

1. Reproduce with `run_trigger_demo.py --debug`
2. Inspect top-k and slot/margin reasons
3. Patch trigger examples or eval hard negatives
4. Re-run:
   - `py -m pytest tests/test_protocol_contracts.py tests/test_sample_cases.py -q`
   - `py cli/eval_trigger_engine.py --dataset data/eval/eval_dataset.jsonl`
5. Compare confusion pairs and false cases in eval report
