from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .compile_check import CompileIssue
from .schemas import FailureCategory, RouteAction


@dataclass
class FailureDecision:
    category: FailureCategory
    action: RouteAction
    reason: str
    fingerprint: str


def fingerprint_error(*, error_type: str, message: str, tool_name: str, subgoal_id: str) -> str:
    normalized = _normalize_text(message)
    raw = f"{error_type}|{normalized}|{tool_name}|{subgoal_id}"
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def classify_failure(
    *,
    subgoal_id: str,
    tool_name: str,
    error_message: str,
    compile_issues: Optional[Iterable[CompileIssue]] = None,
    prior_fingerprints: Optional[Iterable[str]] = None,
) -> FailureDecision:
    text = _normalize_text(error_message)
    error_type = _guess_error_type(text)
    fp = fingerprint_error(
        error_type=error_type,
        message=text,
        tool_name=tool_name,
        subgoal_id=subgoal_id,
    )
    history = list(prior_fingerprints or [])
    if len([x for x in history if x == fp]) >= 1:
        return FailureDecision(
            category=FailureCategory.REPEATED_SAME_ERROR,
            action=RouteAction.CIRCUIT_BREAK,
            reason="same failure fingerprint repeated",
            fingerprint=fp,
        )

    for issue in list(compile_issues or []):
        if str(issue.subgoal_id) != str(subgoal_id):
            continue
        if issue.code in {"input_schema_incomplete", "precondition_not_evaluable"}:
            return FailureDecision(
                category=FailureCategory.MISSING_INPUT,
                action=RouteAction.ASK_USER,
                reason=f"compile issue: {issue.code}",
                fingerprint=fp,
            )

    if _contains_any(text, MISSING_INPUT_KEYWORDS):
        return _decision(FailureCategory.MISSING_INPUT, RouteAction.ASK_USER, "missing runtime input", fp)
    if _contains_any(text, AUTH_ERROR_KEYWORDS):
        return _decision(FailureCategory.AUTH_ERROR, RouteAction.REPAIR_AUTH, "authentication/authorization failure", fp)
    if _contains_any(text, PERMISSION_DENIED_KEYWORDS):
        return _decision(FailureCategory.PERMISSION_DENIED, RouteAction.ASK_USER, "permission denied", fp)
    if _contains_any(text, ENVIRONMENT_MISSING_KEYWORDS):
        return _decision(FailureCategory.ENVIRONMENT_MISSING, RouteAction.ASK_USER, "environment incomplete", fp)
    if is_retryable_error_message(text):
        return _decision(FailureCategory.TRANSIENT_TOOL_ERROR, RouteAction.RETRY, "transient tool failure", fp)
    if _contains_any(text, GOAL_NOT_EXECUTABLE_KEYWORDS):
        return _decision(FailureCategory.GOAL_NOT_EXECUTABLE, RouteAction.ASK_USER, "goal not executable", fp)
    if _contains_any(text, CAPABILITY_GAP_KEYWORDS):
        return _decision(
            FailureCategory.CAPABILITY_GAP,
            RouteAction.LOCAL_REPLAN_WITH_CONSTRAINTS,
            "capability gap",
            fp,
        )
    if _contains_any(text, LOGIC_CONFLICT_KEYWORDS):
        return _decision(FailureCategory.LOGIC_CONFLICT, RouteAction.LOCAL_REPLAN, "logic conflict", fp)
    return _decision(FailureCategory.UNKNOWN, RouteAction.LOCAL_REPLAN, "unknown failure", fp)


def is_retryable_error_message(error_message: str) -> bool:
    return _contains_any(_normalize_text(error_message), RETRYABLE_ERROR_KEYWORDS)


def is_retryable_category(category: FailureCategory) -> bool:
    return category == FailureCategory.TRANSIENT_TOOL_ERROR


def is_retryable_failure(decision: FailureDecision) -> bool:
    return bool(decision.action == RouteAction.RETRY and is_retryable_category(decision.category))


def _decision(category: FailureCategory, action: RouteAction, reason: str, fingerprint: str) -> FailureDecision:
    return FailureDecision(category=category, action=action, reason=reason, fingerprint=fingerprint)


def _normalize_text(text: str) -> str:
    s = str(text or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(k in text for k in keywords)


def _guess_error_type(text: str) -> str:
    if ":" in text:
        return text.split(":", 1)[0].strip()
    if "error" in text:
        return "error"
    return "unknown"


MISSING_INPUT_KEYWORDS = ["missing input", "required", "not provided", "missing required", "keyerror"]
AUTH_ERROR_KEYWORDS = ["401", "403", "unauthorized", "forbidden", "auth", "api key", "token", "credential"]
PERMISSION_DENIED_KEYWORDS = ["permission denied", "permission_denied", "operation not permitted", "eacces", "readonly", "write-protected"]
ENVIRONMENT_MISSING_KEYWORDS = ["module not found", "command not found", "not installed", "missing env", "environment_missing", "file not found", "no such file"]
RETRYABLE_ERROR_KEYWORDS = ["timeout", "timed out", "temporar", "429", "rate limit", "connection reset", "network", "connection refused", "unavailable"]
GOAL_NOT_EXECUTABLE_KEYWORDS = ["goal_not_executable", "objective not executable", "cannot execute goal", "goal is not actionable", "missing acceptance criteria", "ambiguous goal"]
CAPABILITY_GAP_KEYWORDS = ["not implemented", "unsupported", "capability", "cannot do", "model limit"]
LOGIC_CONFLICT_KEYWORDS = ["assertion", "criteria failed", "conflict", "dependency", "logic"]
