# Semantic Trigger Engine MVP

A lightweight MVP for **semantic intent trigger + slot check + decision output**.

This repository provides:
- trigger registry data (`data/triggers/default_triggers.yaml`)
- evaluation dataset (`data/eval/eval_dataset.jsonl`)
- protocol-first tests (`tests/test_protocol_contracts.py`, `tests/test_sample_cases.py`)
- CLI demo/eval entrypoints

## Project Structure

- `src/semantic_trigger/`: engine components (registry, retriever, reranker, calibrator, schemas)
- `data/triggers/default_triggers.yaml`: default trigger definitions
- `data/eval/eval_dataset.jsonl`: evaluation set (trigger / ask_clarification / no_trigger)
- `tests/`: protocol and sample coverage tests
- `cli/run_trigger_demo.py`: run single-query demo
- `cli/eval_trigger_engine.py`: batch evaluate on JSONL dataset
- `docs/debugging.md`: debugging workflow
- `docs/trigger_schema.md`: protocol schema and field semantics

## Quick Demo

```bash
py cli/run_trigger_demo.py --query "明天下午3点提醒我开会" --debug
```

The demo prints:
- decision (`trigger/no_trigger/ask_clarification`)
- selected trigger
- confidence
- extracted/missing slots
- top-k candidates and debug trace (when `--debug`)

## Run Eval

```bash
py cli/eval_trigger_engine.py --dataset data/eval/eval_dataset.jsonl
```

Optional report outputs:

```bash
py cli/eval_trigger_engine.py \
  --dataset data/eval/eval_dataset.jsonl \
  --save-report outputs/report.json \
  --save-trace outputs/trace.jsonl
```

## Run Contract Tests

```bash
py -m pytest tests/test_protocol_contracts.py tests/test_sample_cases.py -q
```

## Add a New Trigger

1. Edit `data/triggers/default_triggers.yaml` and append one trigger entry.
2. Keep required fields:
   - `trigger_id`, `name`, `description`, `aliases`, `positive_examples`, `negative_examples`,
     `required_slots`, `optional_slots`, `enabled`, `tags`
3. Add at least:
   - 3 positive examples
   - 2 hard negatives
   - required slot specs (`slot_name`, `slot_type`, `required`)
4. Add eval rows in `data/eval/eval_dataset.jsonl` for:
   - direct trigger
   - ask_clarification (slot missing/ambiguous)
   - no_trigger confusion samples
5. Re-run tests and eval.

## Notes

- This repo favors **protocol compatibility** over implementation coupling.
- Tests validate schema/data contracts and dataset quality constraints, not model internals.
