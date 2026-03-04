from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

DecisionType = Literal["trigger", "no_trigger", "ask_clarification"]


@dataclass(frozen=True)
class SlotSpec:
    slot_name: str
    slot_type: str = "string"
    required: bool = True
    extraction_hints: List[str] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(obj: Dict[str, Any]) -> "SlotSpec":
        if not isinstance(obj, dict):
            raise ValueError(f"SlotSpec must be dict, got {type(obj).__name__}")
        return SlotSpec(
            slot_name=str(obj.get("slot_name") or obj.get("name") or "").strip(),
            slot_type=str(obj.get("slot_type") or "string").strip(),
            required=bool(obj.get("required", True)),
            extraction_hints=[str(x) for x in (obj.get("extraction_hints") or [])],
            validation_rules=dict(obj.get("validation_rules") or {}),
        )


@dataclass(frozen=True)
class ConstraintSpec:
    constraint_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    @staticmethod
    def from_dict(obj: Dict[str, Any]) -> "ConstraintSpec":
        if not isinstance(obj, dict):
            raise ValueError(f"ConstraintSpec must be dict, got {type(obj).__name__}")
        return ConstraintSpec(
            constraint_type=str(obj.get("constraint_type") or "").strip(),
            params=dict(obj.get("params") or {}),
            description=str(obj.get("description") or ""),
        )


@dataclass
class TriggerDef:
    trigger_id: str
    name: str
    description: str
    aliases: List[str]
    positive_examples: List[str]
    negative_examples: List[str]
    required_slots: List[Dict[str, Any]]
    optional_slots: List[Dict[str, Any]]
    enabled: bool
    tags: List[str]
    # Compatibility-only fields for other local modules.
    hard_constraints: List[ConstraintSpec] = field(default_factory=list)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(obj: Dict[str, Any], index: Optional[int] = None) -> "TriggerDef":
        if not isinstance(obj, dict):
            where = f" at index {index}" if index is not None else ""
            raise ValueError(f"TriggerDef must be dict{where}, got {type(obj).__name__}")

        trigger_id = str(obj.get("trigger_id") or "").strip()
        name = str(obj.get("name") or "").strip()
        description = str(obj.get("description") or "").strip()
        if not trigger_id:
            raise ValueError(_missing("trigger_id", index))
        if not name:
            raise ValueError(_missing("name", index, trigger_id))
        if not description:
            raise ValueError(_missing("description", index, trigger_id))

        return TriggerDef(
            trigger_id=trigger_id,
            name=name,
            description=description,
            aliases=_to_str_list(obj.get("aliases")),
            positive_examples=_to_str_list(obj.get("positive_examples")),
            negative_examples=_to_str_list(obj.get("negative_examples")),
            required_slots=_to_slot_list(obj.get("required_slots"), "required_slots", index, trigger_id),
            optional_slots=_to_slot_list(obj.get("optional_slots"), "optional_slots", index, trigger_id),
            enabled=bool(obj.get("enabled", True)),
            tags=_to_str_list(obj.get("tags")),
            hard_constraints=[ConstraintSpec.from_dict(x) for x in (obj.get("hard_constraints") or [])],
            priority=int(obj.get("priority", 0)),
            metadata=dict(obj.get("metadata") or {}),
        )

    def searchable_text(self) -> str:
        chunks = [
            self.name,
            self.description,
            " ".join(self.aliases),
            " ".join(self.positive_examples),
            " ".join(self.negative_examples),
            " ".join(self.tags),
        ]
        return "\n".join([x for x in chunks if x]).strip()


@dataclass
class CandidateScore:
    trigger_id: str
    recall_score: Optional[float] = None
    rerank_score: Optional[float] = None
    final_score: Optional[float] = None
    notes: Optional[str] = None
    # Compatibility-only fields for existing callers.
    name: str = ""
    reasons: List[str] = field(default_factory=list)

    @property
    def combined_score(self) -> Optional[float]:
        return self.final_score


@dataclass
class EngineResult:
    user_query: str
    decision: DecisionType
    selected_trigger: Optional[str]
    confidence: float
    candidates: List[CandidateScore] = field(default_factory=list)
    extracted_slots: Dict[str, Any] = field(default_factory=dict)
    missing_slots: List[str] = field(default_factory=list)
    clarification_question: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    debug: Dict[str, Any] = field(default_factory=dict)

    @property
    def debug_trace(self) -> Dict[str, Any]:
        return self.debug


# Compatibility alias used by existing modules.
TriggerDecisionResult = EngineResult


def _to_str_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return [str(raw)]
    return [str(x) for x in raw]


def _to_slot_list(
    raw: Any,
    field_name: str,
    index: Optional[int],
    trigger_id: str,
) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        where = f"trigger_id={trigger_id}" if trigger_id else f"index={index}"
        raise ValueError(f"{field_name} must be list ({where})")
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"{field_name}[{i}] must be dict (trigger_id={trigger_id})")
        out.append(dict(item))
    return out


def _missing(field_name: str, index: Optional[int], trigger_id: str = "") -> str:
    if trigger_id:
        return f"TriggerDef.{field_name} is required for trigger_id={trigger_id}"
    if index is None:
        return f"TriggerDef.{field_name} is required"
    return f"TriggerDef.{field_name} is required at index {index}"
