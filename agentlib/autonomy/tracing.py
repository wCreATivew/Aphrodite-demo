from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict


@dataclass
class TraceEvent:
    stage: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


TraceHook = Callable[[TraceEvent], None]


def console_trace_hook(evt: TraceEvent) -> None:
    print(f"[trace:{evt.stage}] {evt.message} | payload={evt.payload}")


# TODO: add bridge to existing metrics/sqlite tracing pipeline when integrating runtime_engine.

