from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List, Set

from .schemas import ExecutableSubgoal, SubgoalState


def compute_descendants(subgoals: Iterable[ExecutableSubgoal], root_id: str) -> Set[str]:
    nodes = list(subgoals)
    children: Dict[str, List[str]] = {}
    for s in nodes:
        for dep in s.dependencies:
            children.setdefault(dep, []).append(s.id)
    out: Set[str] = set()
    stack = [str(root_id)]
    while stack:
        cur = stack.pop()
        if cur in out:
            continue
        out.add(cur)
        for ch in children.get(cur, []):
            if ch not in out:
                stack.append(ch)
    return out


def apply_local_replan(
    *,
    current: Iterable[ExecutableSubgoal],
    failed_id: str,
    replacements: Iterable[ExecutableSubgoal],
) -> List[ExecutableSubgoal]:
    existing = list(current)
    affected = compute_descendants(existing, failed_id)
    frozen_done = {
        s.id
        for s in existing
        if s.state in {SubgoalState.DONE, SubgoalState.SKIPPED}
    }

    kept: List[ExecutableSubgoal] = []
    for s in existing:
        if s.id in affected and s.id not in frozen_done:
            continue
        kept.append(s)

    for repl in list(replacements):
        # Local replan always starts from draft and can be compiled before execution.
        repl.state = SubgoalState.DRAFT
        kept.append(repl)
    return kept


def action_fingerprint(subgoal: ExecutableSubgoal) -> str:
    txt = f"{subgoal.executor_type}|{subgoal.tool_name}|{subgoal.intent}".strip().lower()
    return hashlib.sha1(txt.encode("utf-8", errors="ignore")).hexdigest()

