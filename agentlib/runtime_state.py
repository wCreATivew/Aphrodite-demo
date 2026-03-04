from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict


DEFAULT_STATE: Dict[str, Any] = {
    "emotion": "neutral",
    "affinity": 20,
    "energy": 60,
    "idle_pressure": 0,
    "nudge_count": 0,
    "idle_stage": 0,
    "last_nudge_ts": 0.0,
    "last_turn_ts": None,
    "last_user_ts": None,
    "session_start_ts": None,
    "topic": "smalltalk",
    "topic_prev": "",
    "gap_seconds": None,
    "input_epoch": 0,
}


@dataclass
class RuntimeConfig:
    db_path: str = os.path.join("monitor", "metrics.db")
    state_path: str = "state.json"
    idle_check_interval: float = 1.0
    idle_seconds: int = 20
    nudge_cooldown_sec: int = 90
    max_nudges: int = 3
    rag_top_k: int = 4
    memory_top_k: int = 4
    rag_mode: str = "hybrid"
    max_history_turns: int = 6
    memory_first_enabled: bool = True
    memory_first_strict: bool = False
    persona_profile: str = "aphrodite"
    auto_persona_enabled: bool = True
    persona_switch_min_confidence: float = 0.62
    persona_switch_cooldown_turns: int = 2
    full_user_permissions: bool = True
    screen_capture_enabled: bool = True
    screen_capture_dir: str = os.path.join("monitor", "screenshots")
    ide_watch_enabled: bool = False
    ide_debug_log_path: str = os.path.join("monitor", "ide_debug.log")
    ide_debug_log_max_bytes: int = 2 * 1024 * 1024
    ide_debug_log_backups: int = 3
    ide_watch_poll_interval_sec: float = 1.5
    ide_watch_emit_cooldown_sec: float = 8.0
    ide_auto_fix_enabled: bool = False
    ide_auto_fix_rounds: int = 1
    ide_auto_fix_cooldown_sec: float = 15.0
    ide_auto_fix_only_workspace: bool = True
    ide_auto_fix_mode: str = "continuous"
    ide_auto_fix_loop_cooldown_sec: float = 20.0
    ide_auto_fix_loop_max_cycles: int = 40
    ide_auto_fix_loop_max_no_progress: int = 4
    ide_auto_fix_scope: str = "agentlib,tests"
    ide_auto_fix_smoke_command: str = ""
    ide_auto_fix_require_smoke: bool = False
    ide_auto_fix_count_only_changed: bool = True
    ide_auto_fix_strict_file_relevance: bool = True
    ide_auto_fix_noop_cutoff: int = 2
    ide_auto_fix_ignore_missing_imports: bool = True
    ide_auto_fix_full_scan_on_change: bool = True
    ide_autopilot_enabled: bool = False
    ide_autopilot_command: str = ""
    ide_autopilot_interval_sec: float = 12.0
    ide_autopilot_timeout_sec: float = 120.0
    auto_web_search_enabled: bool = False
    auto_web_search_max_results: int = 3
    auto_web_search_cache_ttl_sec: int = 3600


def load_state(path: str) -> Dict[str, Any]:
    state = dict(DEFAULT_STATE)
    if not os.path.exists(path):
        now = time.time()
        state["session_start_ts"] = now
        state["last_turn_ts"] = now
        state["last_user_ts"] = now
        return state
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            state.update(obj)
    except Exception:
        pass
    now = time.time()
    state["session_start_ts"] = state.get("session_start_ts") or now
    state["last_turn_ts"] = state.get("last_turn_ts") or now
    state["last_user_ts"] = state.get("last_user_ts") or now
    return state


def save_state(path: str, state: Dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def mark_user_turn(state: Dict[str, Any], now_ts: float | None = None) -> None:
    now = float(now_ts or time.time())
    last_user_ts = state.get("last_user_ts")
    gap = None
    if isinstance(last_user_ts, (int, float)):
        gap = max(0.0, now - float(last_user_ts))
    state["gap_seconds"] = gap
    state["last_user_ts"] = now
    state["last_turn_ts"] = now
    state["input_epoch"] = int(state.get("input_epoch", 0) or 0) + 1
    state["idle_stage"] = 0
    state["idle_pressure"] = max(0, int(state.get("idle_pressure", 0) or 0) - 12)


def apply_idle_nudge(state: Dict[str, Any], now_ts: float | None = None) -> int:
    now = float(now_ts or time.time())
    stage = min(3, int(state.get("idle_stage", 0) or 0) + 1)
    state["idle_stage"] = stage
    state["nudge_count"] = int(state.get("nudge_count", 0) or 0) + 1
    state["last_nudge_ts"] = now
    state["idle_pressure"] = min(100, int(state.get("idle_pressure", 0) or 0) + 25)
    return stage


def update_topic(state: Dict[str, Any], user_text: str) -> None:
    t = str(user_text or "").lower()
    prev = str(state.get("topic") or "")
    topic = "smalltalk"
    if any(k in t for k in ["plan", "安排", "todo", "schedule", "日程"]):
        topic = "planning"
    elif any(k in t for k in ["code", "bug", "python", "程序", "开发"]):
        topic = "tech"
    elif any(k in t for k in ["work", "工作", "职业", "职场"]):
        topic = "work"
    elif any(k in t for k in ["sad", "焦虑", "难受", "压力", "生气"]):
        topic = "emotion"
    state["topic_prev"] = prev
    state["topic"] = topic
