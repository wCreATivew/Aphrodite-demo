from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agent_kernel.adapters import CodexCodeAdapter, GLM5PlannerAdapter
from agent_kernel.kernel import AgentKernel
from agent_kernel.planner import V15Planner
from agent_kernel.worker import SpecialistRouterWorker


@dataclass
class SelfDriveSessionState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    active: bool = False
    goal: str = ""
    deadline_ts: float = 0.0
    unbounded: bool = False
    started_ts: float = 0.0
    next_ts: float = 0.0
    last_heartbeat_ts: float = 0.0
    heartbeat_sec: float = 30.0
    step_index: int = 0
    step_gap_sec: float = 20.0
    autonomy_level: str = "L1"
    budget_override_steps: Optional[int] = None
    mode: str = "kernel_v16"
    steps: List[Dict[str, str]] = field(default_factory=list)
    receipt: Dict[str, Any] = field(default_factory=dict)
    file_snapshot: Dict[str, tuple[float, int]] = field(default_factory=dict)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    tests: List[Dict[str, Any]] = field(default_factory=list)
    brief_path: str = ""
    brief_text: str = ""
    heartbeat_log_path: str = os.path.join("outputs", "selfdrive_heartbeat.log")
    api_audit_log_path: str = os.path.join("outputs", "selfdrive_api_audit.log")
    actuation_receipt_log_path: str = os.path.join("outputs", "actuation_receipts.jsonl")


def build_selfdrive_session_state(
    *,
    env_float: Callable[..., float],
    env_str: Callable[..., str],
) -> SelfDriveSessionState:
    return SelfDriveSessionState(
        heartbeat_sec=env_float("SELFDRIVE_HEARTBEAT_SEC", 30.0, min_v=10.0),
        mode=env_str("SELFDRIVE_KERNEL_MODE", "kernel_v16", fallback_on_empty=True),
        heartbeat_log_path=env_str("SELFDRIVE_HEARTBEAT_LOG_PATH", os.path.join("outputs", "selfdrive_heartbeat.log")),
        api_audit_log_path=env_str("SELFDRIVE_API_AUDIT_LOG_PATH", os.path.join("outputs", "selfdrive_api_audit.log")),
        actuation_receipt_log_path=env_str("ACTUATION_RECEIPT_LOG_PATH", os.path.join("outputs", "actuation_receipts.jsonl")),
    )


def build_selfdrive_kernel(
    *,
    planner_adapter: Callable[[str], Dict[str, Any]],
    code_adapter: Callable[[str], Dict[str, Any]],
) -> AgentKernel:
    return AgentKernel(
        planner=V15Planner(),
        worker=SpecialistRouterWorker(
            planner_adapter=GLM5PlannerAdapter(client=planner_adapter),
            code_adapter=CodexCodeAdapter(client=code_adapter),
        ),
    )
