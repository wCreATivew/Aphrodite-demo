from __future__ import annotations

import json
from pathlib import Path

from .schemas import AgentState


def save_state_json(state: AgentState, path: str) -> None:
    p = Path(path)
    if p.parent and (not p.parent.exists()):
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_state_json(path: str) -> AgentState:
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    return AgentState.from_dict(payload)
