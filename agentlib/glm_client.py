from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional

from .env_loader import load_local_env_once

Provider = Literal["openai_compat", "zhipuai", "auto"]

DEFAULT_GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

@dataclass(frozen=True)
class GLMConfig:
    provider: Provider = "auto"
    api_key: str = ""
    base_url: Optional[str] = None
    model: str = "glm-5"
    timeout_sec: float = 60.0
    max_retries: int = 2


class GLMClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        model: str,
        retry_count: int,
        original_error: Exception,
        partial_text: str = "",
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.retry_count = retry_count
        self.original_error = original_error
        self.partial_text = partial_text


class _BackendUnavailableError(RuntimeError):
    pass


def _get_env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def load_glm_config() -> GLMConfig:
    load_local_env_once()
    provider_raw = (
        os.getenv("GLM_PROVIDER")
        or os.getenv("OPENAI_PROVIDER")
        or "auto"
    ).strip().lower()
    if provider_raw == "openai":
        provider_raw = "openai_compat"
    provider: Provider = "auto"
    if provider_raw in {"openai_compat", "zhipuai", "auto"}:
        provider = provider_raw  # type: ignore[assignment]

    api_key = (os.getenv("GLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("GLM_MODEL") or os.getenv("OPENAI_MODEL") or "glm-5").strip() or "glm-5"
    base_url = (os.getenv("GLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip() or DEFAULT_GLM_BASE_URL
    timeout_sec = _get_env_float("GLM_TIMEOUT_SEC", 60.0)
    max_retries = max(0, _get_env_int("GLM_MAX_RETRIES", 2))

    return GLMConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_sec=timeout_sec,
        max_retries=max_retries,
    )


class GLMClient:
    def __init__(self, config: Optional[GLMConfig] = None):
        self.config = config or load_glm_config()

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.8,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        if not self.config.api_key:
            raise GLMClientError(
                "Missing API key. Set GLM_API_KEY (or OPENAI_API_KEY).",
                provider=self.config.provider,
                model=self.config.model,
                retry_count=0,
                original_error=ValueError("missing_api_key"),
            )

        providers: List[Provider]
        if self.config.provider == "auto":
            providers = ["openai_compat", "zhipuai"]
        else:
            providers = [self.config.provider]

        last_error: Optional[Exception] = None
        for provider in providers:
            try:
                yield from self._stream_chat_with_provider(
                    provider=provider,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return
            except _BackendUnavailableError as e:
                last_error = e
                continue
            except GLMClientError:
                raise
            except Exception as e:
                last_error = e
                break

        raise GLMClientError(
            f"All GLM providers failed. provider={self.config.provider}, model={self.config.model}",
            provider=self.config.provider,
            model=self.config.model,
            retry_count=0,
            original_error=last_error or RuntimeError("unknown_error"),
        )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.8,
        max_tokens: Optional[int] = None,
    ) -> str:
        return "".join(
            self.stream_chat(messages=messages, temperature=temperature, max_tokens=max_tokens)
        ).strip()

    def _stream_chat_with_provider(
        self,
        provider: Provider,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Iterator[str]:
        if provider == "openai_compat":
            stream_fn = self._stream_openai_compat
        elif provider == "zhipuai":
            stream_fn = self._stream_zhipuai
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        yield from self._stream_with_retry(
            provider=provider,
            stream_fn=stream_fn,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _stream_with_retry(
        self,
        provider: Provider,
        stream_fn: Callable[[List[Dict[str, Any]], float, Optional[int]], Iterator[str]],
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Iterator[str]:
        retries = max(0, int(self.config.max_retries))
        attempt = 0
        while True:
            partial_chunks: List[str] = []
            try:
                iterator = stream_fn(messages, temperature, max_tokens)
                for piece in iterator:
                    if piece:
                        partial_chunks.append(piece)
                        yield piece
                return
            except _BackendUnavailableError:
                raise
            except Exception as e:
                status = _extract_status_code(e)
                if partial_chunks:
                    raise GLMClientError(
                        (
                            f"Streaming interrupted with partial output. provider={provider}, "
                            f"model={self.config.model}, status={status}"
                        ),
                        provider=provider,
                        model=self.config.model,
                        retry_count=attempt,
                        original_error=e,
                        partial_text="".join(partial_chunks),
                    ) from e

                if _is_auth_error(status) or not _is_retryable_error(e, status) or attempt >= retries:
                    raise GLMClientError(
                        f"GLM request failed. provider={provider}, model={self.config.model}, status={status}",
                        provider=provider,
                        model=self.config.model,
                        retry_count=attempt,
                        original_error=e,
                    ) from e

                time.sleep(0.5 * (2 ** attempt))
                attempt += 1

    def _stream_openai_compat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Iterator[str]:
        try:
            from openai import OpenAI
        except Exception as e:
            raise _BackendUnavailableError("openai package is not available") from e

        try:
            client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url or DEFAULT_GLM_BASE_URL,
                timeout=self.config.timeout_sec,
            )
        except Exception as e:
            raise _BackendUnavailableError("failed to initialize openai-compatible client") from e

        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": float(temperature),
            "stream": True,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = int(max_tokens)

        stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            text = _extract_chunk_text(chunk)
            if text:
                yield text

    def _stream_zhipuai(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Iterator[str]:
        try:
            from zhipuai import ZhipuAI
        except Exception as e:
            raise _BackendUnavailableError("zhipuai package is not available") from e

        try:
            client = ZhipuAI(api_key=self.config.api_key)
        except Exception as e:
            raise _BackendUnavailableError("failed to initialize zhipuai client") from e

        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": float(temperature),
            "stream": True,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = int(max_tokens)

        stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            text = _extract_chunk_text(chunk)
            if text:
                yield text


def _extract_status_code(error: Exception) -> Optional[int]:
    code = getattr(error, "status_code", None)
    if isinstance(code, int):
        return code
    response = getattr(error, "response", None)
    response_code = getattr(response, "status_code", None)
    if isinstance(response_code, int):
        return response_code
    return None


def _is_auth_error(status_code: Optional[int]) -> bool:
    return status_code in (401, 403)


def _is_retryable_error(error: Exception, status_code: Optional[int]) -> bool:
    if status_code == 429:
        return True
    if status_code is not None and status_code >= 500:
        return True
    text = str(error).lower()
    if "timeout" in text or "timed out" in text:
        return True
    if "connection" in text or "temporarily unavailable" in text:
        return True
    return isinstance(error, (TimeoutError, ConnectionError))


def _extract_chunk_text(chunk: Any) -> str:
    if chunk is None:
        return ""

    if isinstance(chunk, dict):
        try:
            choices = chunk.get("choices") or []
            if not choices:
                return ""
            delta = choices[0].get("delta") or {}
            if isinstance(delta, dict):
                return str(delta.get("content") or "")
            return str(getattr(delta, "content", "") or "")
        except Exception:
            return ""

    try:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return ""
        delta = getattr(choices[0], "delta", None)
        if delta is None:
            return ""
        content = getattr(delta, "content", None)
        if content is None:
            return ""
        return str(content)
    except Exception:
        return ""

