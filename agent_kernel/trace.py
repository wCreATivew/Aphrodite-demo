from __future__ import annotations

import time
from typing import Any, Dict


def make_trace_event(event_type: str, **kwargs: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ts": time.time(),
        "event": str(event_type or "unknown"),
    }
    out.update(kwargs)
    return out
