from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Union

from .schemas import ConstraintSpec, TriggerDef

TriggerLike = Union[TriggerDef, Dict[str, Any], None]


@dataclass(frozen=True)
class ConstraintCheckResult:
    ok: bool
    passed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)


def validate_required_slots(trigger_def: TriggerLike, extracted_slots: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Required by protocol.

    Returns:
        missing_slots, reasons
    """
    required_names = _required_slot_names(trigger_def)
    extracted = dict(extracted_slots or {})
    missing: List[str] = []
    reasons: List[str] = []

    for name in required_names:
        value = _resolve_slot_value(name, extracted)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
            reasons.append(f"missing required slot: {name}")
    return missing, reasons


def build_missing_slot_reasons(trigger_def: TriggerLike, extracted_slots: Dict[str, Any]) -> Dict[str, str]:
    missing, _ = validate_required_slots(trigger_def, extracted_slots)
    out: Dict[str, str] = {}
    for slot in missing:
        out[str(slot)] = f"缺少必填槽位 {slot}"
    return out


def validate_simple_constraints(trigger_def: TriggerLike, extracted_slots: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Optional simple slot-level constraints.

    Returns:
        ok, passed_reasons, failed_reasons
    """
    passed: List[str] = []
    failed: List[str] = []

    for spec in _all_slot_specs(trigger_def):
        name = spec.get("slot_name")
        if not name:
            continue
        val = extracted_slots.get(name)
        rules = spec.get("validation_rules") or {}
        slot_type = str(spec.get("slot_type") or "").lower()

        if val is None:
            continue

        if isinstance(rules, dict):
            min_len = rules.get("min_length")
            if isinstance(min_len, int) and isinstance(val, str) and len(val.strip()) < min_len:
                failed.append(f"slot {name}: length<{min_len}")
            if isinstance(min_len, int) and isinstance(val, str) and len(val.strip()) >= min_len:
                passed.append(f"slot {name}: length_ok")

            allowed = rules.get("allowed")
            if isinstance(allowed, list) and allowed:
                allowed_s = {str(x).lower() for x in allowed}
                if str(val).lower() in allowed_s:
                    passed.append(f"slot {name}: allowed_ok")
                else:
                    failed.append(f"slot {name}: not_in_allowed")

        if slot_type == "int":
            if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
                passed.append(f"slot {name}: int_ok")
            else:
                failed.append(f"slot {name}: int_expected")

    return len(failed) == 0, passed, failed


def check_constraints(query: str, trigger: TriggerDef) -> ConstraintCheckResult:
    """
    Backward-compatible query-level hard-constraint checker.
    """
    q = str(query or "").lower()
    passed: List[str] = []
    failed: List[str] = []
    for c in trigger.hard_constraints:
        if _check_one(q, c):
            passed.append(c.constraint_type)
        else:
            failed.append(c.constraint_type)
    return ConstraintCheckResult(ok=(len(failed) == 0), passed=passed, failed=failed)


def _required_slot_names(trigger_def: TriggerLike) -> List[str]:
    if trigger_def is None:
        return []
    if isinstance(trigger_def, TriggerDef):
        out: List[str] = []
        for item in trigger_def.required_slots:
            if isinstance(item, dict):
                name = str(item.get("slot_name") or item.get("name") or "").strip()
            else:
                name = str(getattr(item, "slot_name", "") or "").strip()
            if name:
                out.append(name)
        return out
    if isinstance(trigger_def, dict):
        out: List[str] = []
        for item in trigger_def.get("required_slots") or []:
            if isinstance(item, dict):
                name = str(item.get("slot_name") or item.get("name") or "").strip()
            else:
                name = str(item or "").strip()
            if name:
                out.append(name)
        return out
    return []


def _all_slot_specs(trigger_def: TriggerLike) -> List[Dict[str, Any]]:
    if trigger_def is None:
        return []
    if isinstance(trigger_def, TriggerDef):
        out: List[Dict[str, Any]] = []
        for spec in list(trigger_def.required_slots) + list(trigger_def.optional_slots):
            if isinstance(spec, dict):
                out.append(
                    {
                        "slot_name": str(spec.get("slot_name") or spec.get("name") or "").strip(),
                        "slot_type": str(spec.get("slot_type") or "string").strip(),
                        "validation_rules": dict(spec.get("validation_rules") or {}),
                    }
                )
            else:
                out.append(
                    {
                        "slot_name": str(getattr(spec, "slot_name", "") or "").strip(),
                        "slot_type": str(getattr(spec, "slot_type", "string") or "string").strip(),
                        "validation_rules": dict(getattr(spec, "validation_rules", {}) or {}),
                    }
                )
        return out
    if isinstance(trigger_def, dict):
        out: List[Dict[str, Any]] = []
        for item in (trigger_def.get("required_slots") or []) + (trigger_def.get("optional_slots") or []):
            if isinstance(item, dict):
                out.append(item)
        return out
    return []


def _check_one(query_lower: str, c: ConstraintSpec) -> bool:
    ctype = str(c.constraint_type or "").strip().lower()
    params = dict(c.params or {})
    if ctype == "requires_any_keyword":
        kws = [str(x).lower() for x in (params.get("keywords") or [])]
        return any(k and (k in query_lower) for k in kws)
    if ctype == "forbid_keywords":
        kws = [str(x).lower() for x in (params.get("keywords") or [])]
        return not any(k and (k in query_lower) for k in kws)
    if ctype == "requires_regex":
        patterns = [str(x) for x in (params.get("patterns") or [])]
        return any(re.search(p, query_lower, flags=re.I) for p in patterns if p)
    if ctype == "min_query_length":
        n = int(params.get("n", 1))
        return len(query_lower.strip()) >= n
    return True


def _resolve_slot_value(slot_name: str, extracted_slots: Dict[str, Any]) -> Any:
    canonical = str(slot_name or "").strip().lower()
    aliases = _slot_aliases(canonical)
    for key in aliases:
        if key in extracted_slots:
            return extracted_slots.get(key)
    return None


def _slot_aliases(slot_name: str) -> List[str]:
    base = str(slot_name or "").strip().lower()
    alias_map = {
        "recipient": ["recipient", "contact", "receiver"],
        "contact": ["contact", "recipient", "receiver"],
        "receiver": ["receiver", "recipient", "contact"],
        "content": ["content", "message", "text"],
        "message": ["message", "content", "text"],
        "text": ["text", "content", "message"],
        "time": ["time", "datetime"],
        "datetime": ["datetime", "time"],
        "intent": ["intent", "subject", "topic", "purpose"],
        "subject": ["subject", "intent", "topic", "purpose"],
    }
    return alias_map.get(base, [base])
