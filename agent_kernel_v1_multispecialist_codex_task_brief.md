# Agent Kernel v1 (Multi-Specialist Integration) - Codex Task Brief

## Goal
Build a **runnable Agent Kernel v1** that integrates the user's **existing specialist agents** (already implemented) into a single orchestrated runtime.

This is **not** a greenfield single-worker demo. The objective is to connect the current multi-specialist system to a common kernel loop so the user can continue iterating with their agent.

## Timebox
- Target: **~1 hour** to produce a runnable rough integration.
- Priority order: **runnable integration > preserving current specialist entrypoints > clean interfaces > advanced features**.
- Do not over-design. No heavy framework migration.

---

## What was wrong with the previous skeleton
The previous kernel skeleton was useful as a shape, but it was insufficient for this project because:

1. It used a **single `SimpleWorker` stub** instead of routing to real specialists.
2. It did not define a **specialist registry / adapter layer**.
3. It did not preserve the user's existing specialist APIs and calling conventions.
4. It lacked a **task-to-specialist routing contract**.
5. It did not include a practical fallback path when a specialist is unavailable.

This version fixes that by making **multi-specialist connectivity the first-class requirement**.

---

## Deliverable (must be runnable)
Implement a minimal but working multi-specialist agent kernel with:

1. `AgentState` (structured state)
2. `Task` (typed tasks)
3. `Planner` (simple planner; can bootstrap tasks)
4. `SpecialistRegistry` (register existing experts)
5. `SpecialistRouterWorker` (routes tasks to experts)
6. `Judge` (basic accept/retry/ask-user rules)
7. `AgentKernel` (main loop with checkpoints + trace)
8. `run_kernel_demo.py` (demo entrypoint)

The demo must show that **at least 2 existing specialists can be connected** through adapters (even if one is stubbed/wrapped).

---

## Core design principle
Keep the kernel generic and stable. Put project-specific weirdness in adapters.

- **Kernel owns**: runtime loop, state, task lifecycle, trace, checkpoint
- **Adapters own**: how each existing specialist is called
- **Router owns**: which specialist gets which task

---

## Suggested directory structure

```text
agent_kernel/
  __init__.py
  schemas.py              # AgentState / Task / results / patches
  planner.py              # SimplePlanner
  judge.py                # SimpleJudge
  kernel.py               # AgentKernel loop
  persistence.py          # save/load checkpoint
  trace.py                # trace events

  specialist_registry.py  # Specialist registry + interfaces
  specialist_router.py    # Task -> specialist selection logic
  specialist_adapters.py  # Wrappers around existing experts

run_kernel_demo.py
```

If the project already has similar files, reuse them and only add the missing pieces.

---

## Required interfaces (important)

### 1) Task schema (typed)
Tasks should be explicit and routable.

Minimum fields:
- `task_id`
- `kind` (examples: `semantic_route`, `web_action`, `code_action`, `research`, `ask_user`)
- `description`
- `input_payload`
- `priority`
- `status`
- `retries`

### 2) Specialist adapter contract
Wrap existing experts behind a unified interface.

```python
class SpecialistAdapter(Protocol):
    name: str
    supported_kinds: set[str]

    def can_handle(self, task: Task) -> bool: ...
    def execute(self, task: Task, state: AgentState) -> WorkerResult: ...
```

If Protocol is too much for the timebox, use a base class or duck typing.

### 3) Specialist registry
Must support:
- register(adapter)
- get(name)
- list_all()
- find_candidates(task)

### 4) Router worker
`SpecialistRouterWorker.execute(task, state)` should:
1. ask registry for candidates
2. choose a specialist (simple rules are OK)
3. call adapter.execute(...)
4. normalize return into `WorkerResult`
5. fail gracefully if no specialist is available

---

## How to connect the user's existing specialists (critical)
Do **not** rewrite the specialists. Wrap them.

Examples (adapt to actual code):
- Existing semantic recognition module -> `SemanticRouterAdapter`
- Existing web expert -> `WebSpecialistAdapter`
- Existing code/dev expert -> `CodeSpecialistAdapter`
- Existing research/search expert -> `ResearchSpecialistAdapter`

Each adapter should:
- preserve the original call path
- convert kernel `Task` input -> original specialist input
- convert original specialist output -> `WorkerResult`
- catch exceptions and return structured failures

This is the fastest way to get the kernel running without breaking legacy experts.

---

## Minimal planner behavior (v1)
Planner can be simple. It does not need to be smart yet.

Required behaviors:
1. If there are no tasks, create one initial task from the goal.
2. Select next pending task by priority.
3. (Optional) allow specialists to suggest next tasks and append them.

Example bootstrap strategy:
- If goal text looks like a user request -> create `semantic_route` task first
- Otherwise create `generic_execute` task

---

## Minimal judge behavior (v1)
Judge does not need advanced scoring. It only needs to keep the loop sane.

Rules:
- Worker success -> accept (`task_done`)
- Worker failure -> retry once, then mark failed
- Worker indicates waiting for user -> set state to `waiting_user`
- If budget exceeded -> fail safely

Judge must return a structured result (accepted/retry/ask_user/reason).

---

## Kernel runtime loop (required)
Use this loop shape:

1. `planner.bootstrap(state)`
2. `planner.select_next_task(state)`
3. `router_worker.execute(task, state)`
4. `judge.evaluate(...)`
5. apply `StatePatch`
6. save checkpoint
7. continue / wait / done / fail

### Must-have runtime features
- step budget (`budget_steps_max`)
- trace events (task_started, worker_result, judge_result, state_change)
- checkpoint save every step
- no crash on specialist exception (convert to structured failure)

---

## Compatibility with existing system (must preserve)
The user already has a multi-specialist agent system. Do not break it.

### Requirements
- Keep existing specialist entrypoints intact
- Use adapters instead of refactoring specialists
- Add feature flags or fallback paths if integration is partial
- Avoid changing existing payload shapes unless adapter handles translation

### If integration is blocked
Use a stub adapter *for that specialist only* and continue wiring the kernel.
Do not block the whole kernel waiting for one expert.

---

## Demo requirements (must prove connectivity)
`run_kernel_demo.py` must demonstrate:

1. Create `AgentState(goal=...)`
2. Register at least **2 specialists** (real wrappers or one real + one stub)
3. Run the kernel loop
4. Print:
   - final status
   - steps used
   - executed tasks
   - which specialists were invoked
   - trace length

Bonus (if easy): write checkpoint file and show path.

---

## Recommended file responsibilities

### `specialist_registry.py`
- adapter interface / base class
- registry implementation

### `specialist_router.py`
- routing logic by `task.kind`
- fallback specialist selection
- normalization of outputs

### `specialist_adapters.py`
- wrappers for existing specialists in current project
- exception handling + output normalization

### `kernel.py`
- stays generic (should not know project-specific specialist details)

---

## Output normalization (important for stability)
All specialists should be normalized to return `WorkerResult` with at least:
- `success`
- `task_id`
- `output` (dict)
- `artifacts` (list)
- `error` (optional)
- `suggested_next_tasks` (optional)

This prevents each specialist from breaking the kernel with custom shapes.

---

## Suggested first task kinds (keep small)
Do not support everything in v1. Start with a few:
- `semantic_route`
- `research`
- `web_action`
- `code_action`
- `ask_user`
- `generic_execute`

You can map many real behaviors into these buckets initially.

---

## What NOT to do in this 1-hour pass
- No advanced multi-agent chat orchestration
- No parallel scheduling
- No complex planning algorithms
- No external database
- No full memory system
- No benchmark harness
- No framework migration

This is a kernel integration sprint, not a rewrite.

---

## Acceptance criteria (Definition of Done)
The task is successful if all of the following are true:

1. The kernel runs end-to-end without crashing.
2. At least 2 specialists can be invoked via the registry/router path.
3. The kernel records trace events and saves checkpoint JSON.
4. Specialist failures are caught and represented as structured errors.
5. The code is easy to extend (adapters + router + kernel separation).

---

## Codex execution instructions (copyable)
Use this as the direct instruction to the coding agent:

> Build a runnable Agent Kernel v1 for an existing multi-specialist agent system. Do not replace the specialists. Add a kernel with structured state, task lifecycle, specialist registry, router worker, judge, checkpoints, and trace. Connect at least two existing specialists through adapters. Prioritize runnable integration within ~1 hour. Use adapters to preserve current specialist APIs. No over-design.

---

## Required final output from Codex
Ask Codex to return:
1. Changed file list
2. How to run `run_kernel_demo.py`
3. Demo output summary
4. Which specialists were connected (real vs stub)
5. Current limitations
6. Next 5 improvements (kernel-focused only)

---

## Next-step roadmap (after this v1 works)
Only after this runs:
1. Add `Scheduler` (priority + budget policy)
2. Add `StatePatch` rigor + validation
3. Add `RecoveryPolicy` (retry classes / rollback)
4. Add `Evaluator/Judge` quality scoring
5. Add parallel independent task execution
6. Add persistent memory integration

