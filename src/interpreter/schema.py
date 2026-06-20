from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


def unknown_output(warnings: List[str] | None = None) -> Dict[str, Any]:
    warns = list(warnings or [])
    return {
        "semantic_event": {"event_type": "unknown", "type": "unknown", "topic": None},
        "affective_signal": {"valence": 0.0, "arousal": 0.1},
        "goal_signal": {"explicitness": 0.2, "type": "presence"},
        "relationship_signal": {"dependency_risk": 0.0},
        "memory_trigger_signal": {"memory_type": "none", "type": "none", "strength": 0.1},
        "boundary_signal": {"needs_boundary": False, "sensitivity_raise": 0.2},
        "performance_signal": {"requires_pause": False, "assistant_pull_risk": 0.2},
        "confidence": {"overall": 0.3, "event": 0.3},
        "warnings": warns,
    }


@dataclass
class InterpretedEvent:
    semantic_event: Dict[str, Any] = field(default_factory=dict)
    relationship_signal: Dict[str, Any] = field(default_factory=dict)
    boundary_signal: Dict[str, Any] = field(default_factory=dict)
    memory_trigger_signal: Dict[str, Any] = field(default_factory=dict)
    performance_signal: Dict[str, Any] = field(default_factory=dict)
    confidence: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "semantic_event": dict(self.semantic_event),
            "relationship_signal": dict(self.relationship_signal),
            "boundary_signal": dict(self.boundary_signal),
            "memory_trigger_signal": dict(self.memory_trigger_signal),
            "performance_signal": dict(self.performance_signal),
            "confidence": dict(self.confidence),
            "warnings": list(self.warnings),
        }
