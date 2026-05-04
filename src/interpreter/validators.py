from __future__ import annotations

import math

from .schema import default_interpreted_event


def _clip(v: float, lo: float, hi: float) -> float:
    if math.isnan(v) or math.isinf(v):
        return lo
    return min(hi, max(lo, v))


def _to_float(x, default: float) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    return default


def validate_interpreted_event(payload: dict | None) -> dict:
    out = default_interpreted_event()
    src = payload if isinstance(payload, dict) else {}
    for k in out.keys():
        if k in src and isinstance(out[k], dict) and isinstance(src[k], dict):
            out[k].update(src[k])
    if isinstance(src.get("warnings"), list):
        out["warnings"] = [str(x) for x in src["warnings"]]

    for k in ["valence"]:
        out["affective_signal"][k] = _clip(_to_float(out["affective_signal"].get(k), 0.0), -1.0, 1.0)
    for k in ["arousal", "intensity", "uncertainty"]:
        out["affective_signal"][k] = _clip(_to_float(out["affective_signal"].get(k), 0.0), 0.0, 1.0)

    for section in ["goal_signal", "relationship_signal", "memory_trigger_signal", "performance_signal", "confidence"]:
        for key, value in list(out[section].items()):
            if key in {"memory_type"}:
                continue
            out[section][key] = _clip(_to_float(value, 0.0), 0.0, 1.0)

    for k in ["dependency_risk", "emotional_overload", "over_intimacy_risk"]:
        out["boundary_signal"][k] = _clip(_to_float(out["boundary_signal"].get(k), 0.0), 0.0, 1.0)
    out["boundary_signal"]["needs_boundary"] = bool(out["boundary_signal"].get("needs_boundary", False))
    out["boundary_signal"]["needs_human_redirect"] = bool(out["boundary_signal"].get("needs_human_redirect", False))
    out["boundary_signal"]["dependency_risk"] = out["relationship_signal"]["dependency_risk"]
    out["boundary_signal"]["over_intimacy_risk"] = out["relationship_signal"]["over_intimacy_risk"]

    out["confidence"]["overall"] = _clip(
        min(v for k, v in out["confidence"].items() if k != "overall"), 0.0, 1.0
    )
    return out
