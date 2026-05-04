from __future__ import annotations

from copy import deepcopy

DEFAULT_INTERPRETED_EVENT = {
    "semantic_event": {
        "event_type": "unknown",
        "topic": "general",
        "speech_act": "unknown",
        "explicit_question": False,
        "requires_answer": False,
        "is_user_visible": True,
    },
    "affective_signal": {"valence": 0.0, "arousal": 0.2, "intensity": 0.2, "uncertainty": 0.6},
    "goal_signal": {
        "asks_for_solution": 0.0,
        "asks_for_reassurance": 0.0,
        "asks_for_reflection": 0.0,
        "asks_for_analysis": 0.0,
        "asks_for_presence": 0.0,
        "asks_for_challenge": 0.0,
    },
    "relationship_signal": {
        "recognition_need": 0.2,
        "trust_signal": 0.2,
        "dependency_risk": 0.0,
        "boundary_pressure": 0.0,
        "over_intimacy_risk": 0.0,
        "familiarity_signal": 0.2,
    },
    "memory_trigger_signal": {
        "memory_relevance": 0.1,
        "memory_type": "none",
        "recall_importance": 0.1,
        "emotional_salience": 0.1,
        "self_narrative_relevance": 0.1,
    },
    "boundary_signal": {
        "dependency_risk": 0.0,
        "emotional_overload": 0.0,
        "needs_boundary": False,
        "needs_human_redirect": False,
        "over_intimacy_risk": 0.0,
    },
    "performance_signal": {
        "requires_pause": 0.2,
        "requires_softness": 0.2,
        "requires_stillness": 0.2,
        "requires_direct_eye_contact": 0.2,
        "requires_lightness": 0.2,
    },
    "confidence": {
        "overall": 0.45,
        "semantic_event": 0.45,
        "affective_signal": 0.45,
        "goal_signal": 0.45,
        "relationship_signal": 0.45,
        "memory_trigger_signal": 0.45,
        "boundary_signal": 0.45,
        "performance_signal": 0.45,
    },
    "warnings": [],
}


def default_interpreted_event() -> dict:
    return deepcopy(DEFAULT_INTERPRETED_EVENT)
