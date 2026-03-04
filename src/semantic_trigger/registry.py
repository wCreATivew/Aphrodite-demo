from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schemas import TriggerDef


def load_triggers(path: str, keep_disabled: bool = False) -> List[TriggerDef]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"trigger file not found: {p}")
    obj = _load_yaml_or_json(p)

    raw = obj.get("triggers", obj if isinstance(obj, list) else None)
    if not isinstance(raw, list):
        raise ValueError("trigger file root must be list or {'triggers': list}")

    out: List[TriggerDef] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw):
        trig = TriggerDef.from_dict(item, index=idx)
        if trig.trigger_id in seen:
            raise ValueError(f"duplicate trigger_id: {trig.trigger_id}")
        seen.add(trig.trigger_id)
        if keep_disabled or trig.enabled:
            out.append(trig)
    return out


@dataclass
class TriggerRegistry:
    triggers: List[TriggerDef] = field(default_factory=list)
    by_id: Dict[str, TriggerDef] = field(default_factory=dict)

    @staticmethod
    def from_triggers(triggers: List[TriggerDef]) -> "TriggerRegistry":
        return TriggerRegistry(
            triggers=list(triggers),
            by_id={t.trigger_id: t for t in triggers},
        )

    def enabled_triggers(self) -> List[TriggerDef]:
        return [t for t in self.triggers if t.enabled]

    def get(self, trigger_id: str) -> Optional[TriggerDef]:
        return self.by_id.get(str(trigger_id))


def load_trigger_registry(path: str, keep_disabled: bool = False) -> TriggerRegistry:
    return TriggerRegistry.from_triggers(load_triggers(path, keep_disabled=keep_disabled))


def _load_yaml_or_json(path: Path) -> Dict:
    text = path.read_text(encoding="utf-8-sig")
    try:
        import yaml  # type: ignore

        obj = yaml.safe_load(text)
    except Exception:
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = _parse_minimal_yaml(text)
    if isinstance(obj, list):
        return {"triggers": obj}
    if not isinstance(obj, dict):
        raise ValueError("trigger file root must be mapping/dict or list")
    return obj


def _parse_minimal_yaml(text: str) -> Any:
    lines = _yaml_lines(text)
    if not lines:
        return {}
    value, idx = _parse_node(lines, 0, lines[0][0])
    if idx != len(lines):
        raise ValueError("failed to parse yaml fully")
    return value


def _yaml_lines(text: str) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        out.append((indent, raw.strip()))
    return out


def _parse_node(lines: List[Tuple[int, str]], i: int, indent: int) -> Tuple[Any, int]:
    if i >= len(lines):
        return {}, i
    if lines[i][1].startswith("- "):
        return _parse_list(lines, i, indent)
    return _parse_dict(lines, i, indent)


def _parse_dict(lines: List[Tuple[int, str]], i: int, indent: int) -> Tuple[Dict[str, Any], int]:
    out: Dict[str, Any] = {}
    while i < len(lines):
        cur_indent, txt = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"unexpected indent near: {txt}")
        if txt.startswith("- "):
            break
        key, sep, rest = txt.partition(":")
        if not sep:
            raise ValueError(f"invalid yaml mapping line: {txt}")
        k = key.strip()
        rv = rest.strip()
        i += 1
        if rv:
            out[k] = _parse_scalar(rv)
            continue
        if i < len(lines) and lines[i][0] > cur_indent:
            child, i = _parse_node(lines, i, lines[i][0])
            out[k] = child
        else:
            out[k] = None
    return out, i


def _parse_list(lines: List[Tuple[int, str]], i: int, indent: int) -> Tuple[List[Any], int]:
    out: List[Any] = []
    while i < len(lines):
        cur_indent, txt = lines[i]
        if cur_indent < indent:
            break
        if cur_indent != indent or not txt.startswith("- "):
            break
        rest = txt[2:].strip()
        i += 1
        if not rest:
            if i < len(lines) and lines[i][0] > cur_indent:
                child, i = _parse_node(lines, i, lines[i][0])
                out.append(child)
            else:
                out.append(None)
            continue

        if _looks_like_inline_mapping(rest):
            key, _, after = rest.partition(":")
            item: Dict[str, Any] = {key.strip(): _parse_scalar(after.strip()) if after.strip() else None}
            if i < len(lines) and lines[i][0] > cur_indent:
                child, i = _parse_node(lines, i, lines[i][0])
                if isinstance(child, dict):
                    item.update(child)
                elif child is not None:
                    item["_value"] = child
            out.append(item)
            continue

        out.append(_parse_scalar(rest))
    return out, i


def _looks_like_inline_mapping(text: str) -> bool:
    if text.startswith('"') or text.startswith("'") or text.startswith("[") or text.startswith("{"):
        return False
    return ":" in text


def _parse_scalar(text: str) -> Any:
    t = text.strip()
    low = t.lower()
    if low in {"true", "false"}:
        return low == "true"
    if low in {"null", "none", "~"}:
        return None
    if re.fullmatch(r"[+-]?\d+", t):
        try:
            return int(t)
        except Exception:
            pass
    if re.fullmatch(r"[+-]?\d+\.\d+", t):
        try:
            return float(t)
        except Exception:
            pass
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        try:
            return ast.literal_eval(t)
        except Exception:
            return t[1:-1]
    if (t.startswith("[") and t.endswith("]")) or (t.startswith("{") and t.endswith("}")):
        try:
            return json.loads(t)
        except Exception:
            try:
                return ast.literal_eval(t)
            except Exception:
                return t
    return t
