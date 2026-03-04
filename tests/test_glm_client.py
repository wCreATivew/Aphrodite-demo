from __future__ import annotations

import os
import sys
import unittest
import importlib.util
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


glm_mod = _load_module("agentlib.glm_client", ROOT / "agentlib" / "glm_client.py")
if "agentlib" not in sys.modules:
    pkg = types.ModuleType("agentlib")
    pkg.__path__ = [str(ROOT / "agentlib")]
    sys.modules["agentlib"] = pkg
sys.modules["agentlib"].glm_client = glm_mod
DEFAULT_GLM_BASE_URL = glm_mod.DEFAULT_GLM_BASE_URL
GLMClient = glm_mod.GLMClient
GLMClientError = glm_mod.GLMClientError
GLMConfig = glm_mod.GLMConfig
_BackendUnavailableError = glm_mod._BackendUnavailableError
_extract_chunk_text = glm_mod._extract_chunk_text
load_glm_config = glm_mod.load_glm_config


class _StatusError(Exception):
    def __init__(self, status_code: int, message: str = "error"):
        super().__init__(message)
        self.status_code = status_code


class GLMConfigTests(unittest.TestCase):
    def test_load_glm_config_defaults(self):
        with patch.dict(os.environ, {"GLM_API_KEY": "k1"}, clear=True):
            cfg = load_glm_config()
        self.assertEqual(cfg.provider, "auto")
        self.assertEqual(cfg.api_key, "k1")
        self.assertEqual(cfg.model, "glm-5")
        self.assertEqual(cfg.base_url, DEFAULT_GLM_BASE_URL)
        self.assertEqual(cfg.timeout_sec, 60.0)
        self.assertEqual(cfg.max_retries, 2)

    def test_load_glm_config_provider_override(self):
        with patch.dict(
            os.environ,
            {
                "GLM_PROVIDER": "zhipuai",
                "GLM_API_KEY": "k1",
                "GLM_MODEL": "glm-5-plus",
            },
            clear=True,
        ):
            cfg = load_glm_config()
        self.assertEqual(cfg.provider, "zhipuai")
        self.assertEqual(cfg.model, "glm-5-plus")

    def test_load_glm_config_openai_fallbacks(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_PROVIDER": "openai",
                "OPENAI_API_KEY": "ok1",
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
                "OPENAI_MODEL": "gpt-5-mini",
            },
            clear=True,
        ):
            cfg = load_glm_config()
        self.assertEqual(cfg.provider, "openai_compat")
        self.assertEqual(cfg.api_key, "ok1")
        self.assertEqual(cfg.base_url, "https://api.openai.com/v1")
        self.assertEqual(cfg.model, "gpt-5-mini")


class GLMClientTests(unittest.TestCase):
    def setUp(self):
        self.messages = [{"role": "user", "content": "hi"}]

    def test_missing_api_key_raises(self):
        client = GLMClient(GLMConfig(provider="openai_compat", api_key=""))
        with self.assertRaises(GLMClientError) as ctx:
            list(client.stream_chat(self.messages))
        self.assertIn("Missing API key", str(ctx.exception))

    def test_auto_fallback_to_zhipu_when_openai_unavailable(self):
        client = GLMClient(GLMConfig(provider="auto", api_key="k"))
        calls = []

        def fake(provider, messages, temperature, max_tokens):
            calls.append(provider)
            if provider == "openai_compat":
                raise _BackendUnavailableError("openai unavailable")
            return iter(["ok"])

        with patch.object(client, "_stream_chat_with_provider", side_effect=fake):
            out = "".join(client.stream_chat(self.messages))
        self.assertEqual(out, "ok")
        self.assertEqual(calls, ["openai_compat", "zhipuai"])

    def test_retry_on_429_then_success(self):
        client = GLMClient(GLMConfig(provider="openai_compat", api_key="k", max_retries=2))
        counter = {"n": 0}

        def fake(messages, temperature, max_tokens):
            if counter["n"] == 0:
                counter["n"] += 1
                raise _StatusError(429, "rate limit")
            return iter(["A", "B"])

        with patch.object(client, "_stream_openai_compat", side_effect=fake):
            with patch("agentlib.glm_client.time.sleep", return_value=None):
                out = "".join(client.stream_chat(self.messages))
        self.assertEqual(out, "AB")
        self.assertEqual(counter["n"], 1)

    def test_auth_error_is_not_retried(self):
        client = GLMClient(GLMConfig(provider="openai_compat", api_key="k", max_retries=3))
        counter = {"n": 0}

        def fake(messages, temperature, max_tokens):
            counter["n"] += 1
            raise _StatusError(401, "unauthorized")

        with patch.object(client, "_stream_openai_compat", side_effect=fake):
            with self.assertRaises(GLMClientError) as ctx:
                list(client.stream_chat(self.messages))
        self.assertIn("status=401", str(ctx.exception))
        self.assertEqual(counter["n"], 1)

    def test_partial_stream_error_keeps_partial_text(self):
        client = GLMClient(GLMConfig(provider="openai_compat", api_key="k", max_retries=1))

        def fake(messages, temperature, max_tokens):
            yield "hello"
            raise _StatusError(500, "server error")

        with patch.object(client, "_stream_openai_compat", side_effect=fake):
            with self.assertRaises(GLMClientError) as ctx:
                list(client.stream_chat(self.messages))
        self.assertEqual(ctx.exception.partial_text, "hello")


class ChunkExtractionTests(unittest.TestCase):
    def test_extract_chunk_text_from_dict(self):
        chunk = {"choices": [{"delta": {"content": "abc"}}]}
        self.assertEqual(_extract_chunk_text(chunk), "abc")

    def test_extract_chunk_text_from_object(self):
        class Delta:
            content = "xyz"

        class Choice:
            delta = Delta()

        class Chunk:
            choices = [Choice()]

        self.assertEqual(_extract_chunk_text(Chunk()), "xyz")


if __name__ == "__main__":
    unittest.main()
