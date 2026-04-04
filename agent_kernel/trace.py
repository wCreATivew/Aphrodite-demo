from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


def make_trace_event(
    event_type: str,
    *,
    scene_delta: Optional[Dict[str, Any]] = None,
    scene_deltas: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ts": time.time(),
        "event": str(event_type or "unknown"),
    }
    out.update(kwargs)
    if scene_delta is not None:
        out["scene_delta"] = dict(scene_delta)
    if scene_deltas:
        out["scene_deltas"] = [dict(x) for x in scene_deltas]
    return out
