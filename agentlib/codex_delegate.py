from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .env_loader import load_local_env_once


@dataclass(frozen=True)
class CodexDelegateConfig:
    enabled: bool = True
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.2-codex"
    timeout_sec: float = 90.0
    api_surface: str = "responses"
    allow_chat_fallback: bool = False
    max_retries: int = 0
    fast_timeout_sec: float = 20.0
    deep_timeout_sec: float = 90.0
    fast_reasoning_effort: str = "low"
    deep_reasoning_effort: str = "medium"


@dataclass(frozen=True)
class CodexDelegateResult:
    ok: bool
    execution_task: str
    notes: str = ""
    risk: str = ""
    raw_text: str = ""


def load_codex_delegate_config() -> CodexDelegateConfig:
    load_local_env_once()

    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return bool(default)
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def _env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return float(default)
        try:
            return float(raw)
        except Exception:
            return float(default)

    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return int(default)

    def _effort(value: str, default: str) -> str:
        v = str(value or default).strip().lower()
        if v in {"minimal", "low", "medium", "high"}:
            return v
        return str(default).strip().lower()
        try:
            return int(raw)
        except Exception:
            return int(default)

    api_surface = (
        os.getenv("CODEX_API_SURFACE")
        or os.getenv("OPENAI_API_SURFACE")
        or "responses"
    ).strip().lower()
    if api_surface not in {"responses", "chat", "auto"}:
        api_surface = "responses"

    return CodexDelegateConfig(
        enabled=_env_bool("CODEX_DELEGATE_ENABLED", True),
        api_key=(os.getenv("CODEX_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
        base_url=(os.getenv("CODEX_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip(),
        model=(os.getenv("CODEX_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.2-codex").strip(),
        timeout_sec=_env_float("CODEX_TIMEOUT_SEC", 90.0),
        api_surface=api_surface,
        allow_chat_fallback=_env_bool("CODEX_ALLOW_CHAT_FALLBACK", False),
        max_retries=max(0, _env_int("CODEX_MAX_RETRIES", 0)),
        fast_timeout_sec=max(1.0, _env_float("CODEX_FAST_TIMEOUT_SEC", 20.0)),
        deep_timeout_sec=max(1.0, _env_float("CODEX_DEEP_TIMEOUT_SEC", _env_float("CODEX_TIMEOUT_SEC", 90.0))),
        fast_reasoning_effort=_effort(os.getenv("CODEX_FAST_REASONING_EFFORT", "low"), "low"),
        deep_reasoning_effort=_effort(os.getenv("CODEX_DEEP_REASONING_EFFORT", "medium"), "medium"),
    )


def _extract_json_dict(text: str) -> Optional[Dict[str, Any]]:
    t = str(text or "").strip()
    if not t:
        return None
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    l = t.find("{")
    r = t.rfind("}")
    if l >= 0 and r > l:
        try:
            obj = json.loads(t[l : r + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None


def _normalize_delegate_error_signature(text: str) -> str:
    t = str(text or "").strip().lower()
    if not t:
        return "execution_error:empty_error"
    if any(
        k in t
        for k in [
            "not a chat model",
            "chat/completions endpoint",
            "did you mean to use v1/completions",
            "responses api",
        ]
    ):
        return f"endpoint_mismatch:{text}"
    if any(k in t for k in ["timeout", "timed out", "deadline", "read timeout", "connect timeout"]):
        return f"timeout:{text}"
    if any(k in t for k in ["401", "403", "unauthorized", "forbidden", "api key", "auth", "token", "credential"]):
        return f"auth:{text}"
    if any(k in t for k in ["json", "parse", "decode", "invalid response format", "schema"]):
        return f"parse_error:{text}"
    if any(k in t for k in ["permission denied", "access denied", "forbidden by policy", "not allowed"]):
        return f"permission_denied:{text}"
    if any(k in t for k in ["module not found", "no module named", "command not found", "not installed", "missing env"]):
        return f"environment_missing:{text}"
    return f"execution_error:{text}"


def _normalize_exception_signature(exc: BaseException) -> str:
    msg = f"{type(exc).__name__}: {exc}"
    return _normalize_delegate_error_signature(msg)


def _sanitize_json_for_contract(obj: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(obj or {})
    if "_delegate_error" in out:
        out["_delegate_error"] = _normalize_delegate_error_signature(str(out.get("_delegate_error") or ""))
    if "_delegate_error_category" in out:
        out["_delegate_error_category"] = str(out.get("_delegate_error_category") or "").strip().lower()
    return out


def _extract_text_from_response(resp: Any) -> str:
    # Newer SDKs expose a convenience property.
    txt = str(getattr(resp, "output_text", "") or "").strip()
    if txt:
        return txt

    parts: list[str] = []

    def _append_text(value: Any) -> None:
        t = str(value or "").strip()
        if t:
            parts.append(t)

    # Dict-like fallback.
    if isinstance(resp, dict):
        out = list(resp.get("output") or [])
        for item in out:
            content = []
            if isinstance(item, dict):
                content = list(item.get("content") or [])
            for c in content:
                if isinstance(c, dict):
                    _append_text(c.get("text"))
        return "\n".join(parts).strip()

    # Object-like fallback.
    for item in list(getattr(resp, "output", []) or []):
        content = list(getattr(item, "content", []) or [])
        for c in content:
            _append_text(getattr(c, "text", ""))
    return "\n".join(parts).strip()


class CodexDelegateClient:
    def __init__(self, config: Optional[CodexDelegateConfig] = None):
        self.cfg = config or load_codex_delegate_config()

    def try_chat_json(
        self,
        *,
        system: str,
        user_payload: Dict[str, Any],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        with_error: bool = False,
        timeout_sec_override: Optional[float] = None,
        execution_lane: str = "deep",
        reasoning_effort_override: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not bool(self.cfg.enabled):
            if with_error:
                return {
                    "_delegate_error": "environment_missing:delegate disabled",
                    "_delegate_error_category": "environment_missing",
                }
            return None
        if not self.cfg.api_key:
            if with_error:
                return {
                    "_delegate_error": "auth:missing CODEX_API_KEY/OPENAI_API_KEY",
                    "_delegate_error_category": "auth",
                }
            return None
        try:
            from openai import OpenAI
        except Exception as e:
            if with_error:
                return {
                    "_delegate_error": _normalize_exception_signature(e),
                    "_delegate_error_category": "environment_missing",
                }
            return None
        try:
            lane = str(execution_lane or "deep").strip().lower()
            if lane not in {"fast", "deep"}:
                lane = "deep"
            timeout_sec = float(self.cfg.fast_timeout_sec if lane == "fast" else self.cfg.deep_timeout_sec)
            if timeout_sec_override is not None:
                try:
                    timeout_sec = max(1.0, float(timeout_sec_override))
                except Exception:
                    timeout_sec = float(self.cfg.timeout_sec)
            reasoning_effort = str(
                reasoning_effort_override
                or (self.cfg.fast_reasoning_effort if lane == "fast" else self.cfg.deep_reasoning_effort)
            ).strip().lower()
            if reasoning_effort not in {"minimal", "low", "medium", "high"}:
                reasoning_effort = "medium"
            client = OpenAI(
                api_key=self.cfg.api_key,
                base_url=self.cfg.base_url,
                timeout=timeout_sec,
                max_retries=max(0, int(self.cfg.max_retries)),
            )
            raw = ""
            requested_surface = str(self.cfg.api_surface or "responses").strip().lower()
            if requested_surface not in {"responses", "chat", "auto"}:
                requested_surface = "responses"
            tried_responses = False
            responses_error: Optional[Exception] = None

            if requested_surface in {"responses", "auto"}:
                tried_responses = True
                try:
                    rsp_kwargs: Dict[str, Any] = {
                        "model": self.cfg.model,
                        "input": [
                            {
                                "role": "system",
                                "content": [{"type": "text", "text": str(system or "").strip()}],
                            },
                            {
                                "role": "user",
                                "content": [{"type": "text", "text": json.dumps(user_payload or {}, ensure_ascii=False)}],
                            },
                        ],
                        "temperature": float(temperature),
                    }
                    if max_tokens is not None:
                        rsp_kwargs["max_output_tokens"] = int(max_tokens)
                    if reasoning_effort:
                        rsp_kwargs["reasoning"] = {"effort": reasoning_effort}
                    try:
                        resp = client.responses.create(**rsp_kwargs)
                    except Exception:
                        # Some provider-compatible endpoints may not accept reasoning options.
                        if "reasoning" in rsp_kwargs:
                            rsp_kwargs.pop("reasoning", None)
                            resp = client.responses.create(**rsp_kwargs)
                        else:
                            raise
                    raw = _extract_text_from_response(resp)
                except Exception as e:
                    responses_error = e
                    can_fallback_to_chat = (
                        requested_surface == "auto"
                        and bool(self.cfg.allow_chat_fallback)
                    )
                    if not can_fallback_to_chat:
                        raise

            if not raw and requested_surface in {"chat", "auto"}:
                kwargs: Dict[str, Any] = {
                    "model": self.cfg.model,
                    "messages": [
                        {"role": "system", "content": str(system or "").strip()},
                        {"role": "user", "content": json.dumps(user_payload or {}, ensure_ascii=False)},
                    ],
                    "temperature": float(temperature),
                }
                if max_tokens is not None:
                    kwargs["max_tokens"] = int(max_tokens)
                try:
                    resp = client.chat.completions.create(**kwargs)
                except Exception:
                    # If responses was tried first, preserve first error for diagnosis.
                    if responses_error is not None:
                        raise responses_error
                    raise
                raw = str((resp.choices[0].message.content if resp and resp.choices else "") or "").strip()

            if not raw and tried_responses and responses_error is not None:
                raise responses_error
        except Exception as e:
            if with_error:
                return {
                    "_delegate_error": _normalize_exception_signature(e),
                    "_delegate_error_category": "execution_error",
                }
            return None
        obj = _extract_json_dict(raw)
        if isinstance(obj, dict):
            return _sanitize_json_for_contract(obj)
        if with_error:
            return {
                "_delegate_error": _normalize_delegate_error_signature("parse_error:invalid json from delegate"),
                "_delegate_error_category": "parse_error",
                "_raw_text": str(raw or "")[:2000],
            }
        return None

    def delegate_task(self, *, project_goal: str, task: str, context: str = "") -> CodexDelegateResult:
        base_task = str(task or "").strip()
        if not base_task:
            return CodexDelegateResult(ok=False, execution_task="", notes="empty task")
        if not bool(self.cfg.enabled):
            return CodexDelegateResult(ok=False, execution_task=base_task, notes="delegate disabled")
        if not self.cfg.api_key:
            return CodexDelegateResult(ok=False, execution_task=base_task, notes="missing CODEX_API_KEY/OPENAI_API_KEY")
        try:
            import openai  # noqa: F401
        except Exception:
            return CodexDelegateResult(ok=False, execution_task=base_task, notes="openai package unavailable")

        system = (
            "You are Codex executor. Convert a high-level task into one concrete, implementable coding assignment. "
            "Return strict JSON with keys: execution_task, notes, risk. "
            "execution_task must be specific and directly executable by a coding agent."
        )
        user_payload = {
            "project_goal": str(project_goal or "").strip(),
            "task": base_task,
            "context": str(context or "").strip()[:2000],
            "constraints": [
                "Keep scope small but complete",
                "Prefer modifications inside current workspace",
                "Include acceptance criteria in execution_task",
            ],
        }
        obj = self.try_chat_json(
            system=system,
            user_payload=user_payload,
            temperature=0.2,
            max_tokens=360,
        )
        if not obj:
            return CodexDelegateResult(
                ok=False,
                execution_task=base_task,
                notes="invalid json from codex (or codex unavailable)",
            )
        execution_task = str(obj.get("execution_task") or "").strip()
        notes = str(obj.get("notes") or "").strip()
        risk = str(obj.get("risk") or "").strip()
        if not execution_task:
            return CodexDelegateResult(ok=False, execution_task=base_task, notes="empty execution_task", risk=risk)
        return CodexDelegateResult(ok=True, execution_task=execution_task, notes=notes, risk=risk, raw_text="")
