from __future__ import annotations

import json
import os
import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class EngineConfig:
    top_k: int = 8
    # Decision policy thresholds (phase-2 canonical names).
    accept_threshold: float = 0.55
    clarify_threshold: float = 0.42
    margin_threshold: float = 0.08
    no_trigger_floor: float = 0.25
    per_trigger_accept_threshold: Dict[str, float] = field(default_factory=dict)
    # Legacy names kept for compatibility.
    no_trigger_threshold: float = 0.25
    ask_clarification_margin: float = 0.08
    trigger_threshold: float = 0.50
    min_trigger_margin: float = 0.02
    keep_disabled: bool = False
    # Compatibility fields for existing modules/config readers.
    rerank_top_k: int = 8
    low_confidence_threshold: float = 0.45
    margin_threshold_legacy: float = 0.08
    min_consistency_score: float = 0.20
    default_trigger_threshold: float = 0.50
    per_trigger_threshold: Dict[str, float] = field(default_factory=dict)
    enable_adjudicator: bool = False
    log_level: str = "INFO"
    json_log: bool = False
    config_version: str = "v1"
    policy_version: str = "v1"
    dataset_version: str = "unknown"


# Compatibility alias used by existing modules.
AppConfig = EngineConfig


def load_config(path: str = "") -> EngineConfig:
    if not path:
        return EngineConfig(
            top_k=_env_int("STE_TOP_K", 8),
            accept_threshold=_env_float("STE_ACCEPT_THRESHOLD", _env_float("STE_TRIGGER_THRESHOLD", 0.55)),
            clarify_threshold=_env_float("STE_CLARIFY_THRESHOLD", _env_float("STE_LOW_CONF", 0.42)),
            margin_threshold=_env_float("STE_MARGIN_THRESHOLD", 0.08),
            no_trigger_floor=_env_float("STE_NO_TRIGGER_FLOOR", _env_float("STE_NO_TRIGGER_THRESHOLD", 0.25)),
            per_trigger_accept_threshold={},
            no_trigger_threshold=_env_float("STE_NO_TRIGGER_THRESHOLD", 0.25),
            ask_clarification_margin=_env_float("STE_ASK_CLARIFICATION_MARGIN", 0.08),
            trigger_threshold=_env_float("STE_TRIGGER_THRESHOLD", 0.50),
            min_trigger_margin=_env_float("STE_MIN_TRIGGER_MARGIN", 0.02),
            keep_disabled=_env_bool("STE_KEEP_DISABLED", False),
            rerank_top_k=_env_int("STE_RERANK_TOP_K", 8),
            low_confidence_threshold=_env_float("STE_LOW_CONF", 0.45),
            margin_threshold_legacy=_env_float("STE_MARGIN_THRESHOLD", 0.08),
            min_consistency_score=_env_float("STE_MIN_CONSISTENCY", 0.20),
            default_trigger_threshold=_env_float("STE_DEFAULT_TRIGGER_THRESHOLD", 0.50),
            per_trigger_threshold={},
            enable_adjudicator=_env_bool("STE_ENABLE_ADJUDICATOR", False),
            log_level=str(os.getenv("STE_LOG_LEVEL", "INFO")),
            json_log=_env_bool("STE_JSON_LOG", False),
            config_version=str(os.getenv("STE_CONFIG_VERSION", "v1")),
            policy_version=str(os.getenv("STE_POLICY_VERSION", "v1")),
            dataset_version=str(os.getenv("STE_DATASET_VERSION", "unknown")),
        )

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config file not found: {p}")
    obj = _load_yaml_or_json(p)

    return EngineConfig(
        top_k=int(obj.get("top_k", 8)),
        accept_threshold=float(obj.get("accept_threshold", obj.get("trigger_threshold", 0.55))),
        clarify_threshold=float(obj.get("clarify_threshold", obj.get("low_confidence_threshold", 0.42))),
        margin_threshold=float(obj.get("margin_threshold", 0.08)),
        no_trigger_floor=float(obj.get("no_trigger_floor", obj.get("no_trigger_threshold", 0.25))),
        per_trigger_accept_threshold={
            str(k): float(v) for k, v in dict(obj.get("per_trigger_accept_threshold") or obj.get("per_trigger_threshold") or {}).items()
        },
        no_trigger_threshold=float(obj.get("no_trigger_threshold", 0.25)),
        ask_clarification_margin=float(obj.get("ask_clarification_margin", 0.08)),
        trigger_threshold=float(obj.get("trigger_threshold", 0.50)),
        min_trigger_margin=float(obj.get("min_trigger_margin", 0.02)),
        keep_disabled=bool(obj.get("keep_disabled", False)),
        rerank_top_k=int(obj.get("rerank_top_k", obj.get("top_k", 8))),
        low_confidence_threshold=float(obj.get("low_confidence_threshold", 0.45)),
        margin_threshold_legacy=float(obj.get("margin_threshold", 0.08)),
        min_consistency_score=float(obj.get("min_consistency_score", 0.20)),
        default_trigger_threshold=float(obj.get("default_trigger_threshold", 0.50)),
        per_trigger_threshold={str(k): float(v) for k, v in dict(obj.get("per_trigger_threshold") or {}).items()},
        enable_adjudicator=bool(obj.get("enable_adjudicator", False)),
        log_level=str(obj.get("log_level", "INFO")),
        json_log=bool(obj.get("json_log", False)),
        config_version=str(obj.get("config_version", "v1")),
        policy_version=str(obj.get("policy_version", "v1")),
        dataset_version=str(obj.get("dataset_version", "unknown")),
    )


# Compatibility alias used by existing modules.
load_app_config = load_config


def _load_yaml_or_json(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        import yaml  # type: ignore

        obj = yaml.safe_load(text)
    except Exception:
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = _parse_minimal_yaml(text)
    if not isinstance(obj, dict):
        raise ValueError("config root must be mapping/dict")
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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)
