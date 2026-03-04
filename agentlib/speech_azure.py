from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AzureSpeechConfig:
    enabled_tts: bool = False
    enabled_stt: bool = False
    speech_key_env: str = "AZURE_SPEECH_KEY"
    speech_region_env: str = "AZURE_SPEECH_REGION"
    speech_region_default: str = "eastus"
    tts_output_format: str = "riff-24khz-16bit-mono-pcm"
    stt_language: str = "zh-CN"
    tts_save_path: str = os.path.join("monitor", "tts_last.wav")
    ssml_voice: str = "zh-CN-XiaoxiaoNeural"
    ssml_style: str = "newscast"
    ssml_styledegree: float = 0.6
    ssml_role: Optional[str] = None
    ssml_volume: str = "default"
    ssml_lang: str = "zh-CN"
    ssml_use_mstts: bool = True


def load_azure_speech_config() -> AzureSpeechConfig:
    return AzureSpeechConfig(
        enabled_tts=_env_bool("AZURE_TTS_ENABLED", False),
        enabled_stt=_env_bool("AZURE_STT_ENABLED", False),
        speech_key_env=(os.getenv("AZURE_SPEECH_KEY_ENV") or "AZURE_SPEECH_KEY").strip(),
        speech_region_env=(os.getenv("AZURE_SPEECH_REGION_ENV") or "AZURE_SPEECH_REGION").strip(),
        speech_region_default=(os.getenv("AZURE_SPEECH_REGION_DEFAULT") or "eastus").strip(),
        tts_output_format=(os.getenv("AZURE_TTS_OUTPUT_FORMAT") or "riff-24khz-16bit-mono-pcm").strip(),
        stt_language=(os.getenv("AZURE_STT_LANGUAGE") or "zh-CN").strip(),
        tts_save_path=(os.getenv("AZURE_TTS_SAVE_PATH") or os.path.join("monitor", "tts_last.wav")).strip(),
        ssml_voice=(os.getenv("SSML_VOICE") or "zh-CN-XiaoxiaoNeural").strip(),
        ssml_style=(os.getenv("SSML_STYLE") or "newscast").strip(),
        ssml_styledegree=_env_float("SSML_STYLEDEGREE", 0.6),
        ssml_role=(os.getenv("SSML_ROLE") or "").strip() or None,
        ssml_volume=(os.getenv("SSML_VOLUME") or "default").strip(),
        ssml_lang=(os.getenv("SSML_LANG") or "zh-CN").strip(),
        ssml_use_mstts=_env_bool("SSML_USE_MSTTS", True),
    )


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


def _xml_escape(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _azure_region(cfg: AzureSpeechConfig) -> str:
    raw = os.getenv(cfg.speech_region_env) or cfg.speech_region_default
    r = str(raw or "").strip().lower().replace(" ", "")
    return r or "eastus"


def _azure_speech_key(cfg: AzureSpeechConfig) -> str:
    return str(os.getenv(cfg.speech_key_env) or "").strip()


def detect_ssml_unsupported(error_text: str) -> Dict[str, bool]:
    t = (error_text or "").lower()
    return {
        "drop_style": any(k in t for k in ["style", "express-as", "mstts"]),
        "drop_role": any(k in t for k in ["role", "speaker", "style role"]),
        "drop_mstts": any(k in t for k in ["mstts", "express-as", "not supported", "unsupported"]),
    }


def render_ssml(text_raw: str, prosody: Dict[str, str], meta: Dict[str, Any], cfg: AzureSpeechConfig) -> Dict[str, Any]:
    voice = str(meta.get("voice") or cfg.ssml_voice)
    style = str(meta.get("style") or cfg.ssml_style)
    styledegree = meta.get("styledegree") if meta.get("styledegree") is not None else cfg.ssml_styledegree
    role = meta.get("role") if meta.get("role") is not None else cfg.ssml_role
    volume = str(meta.get("volume") or cfg.ssml_volume)
    if "db" in volume.lower():
        volume = "default"
    lang = str(meta.get("lang") or cfg.ssml_lang)
    use_mstts = meta.get("use_mstts") if meta.get("use_mstts") is not None else cfg.ssml_use_mstts

    body = _xml_escape(text_raw or "")
    rate = str(prosody.get("rate") or "100%")
    pitch = str(prosody.get("pitch") or "0%")

    if use_mstts and style:
        role_attr = f' role="{_xml_escape(str(role))}"' if role else ""
        ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="{_xml_escape(lang)}">'
            f'<voice name="{_xml_escape(voice)}">'
            f'<mstts:express-as style="{_xml_escape(style)}" styledegree="{styledegree}"{role_attr}>'
            f'<prosody rate="{_xml_escape(rate)}" pitch="{_xml_escape(pitch)}" volume="{_xml_escape(volume)}">'
            f"{body}"
            f"</prosody>"
            f"</mstts:express-as>"
            f"</voice>"
            f"</speak>"
        )
        return {"ssml": ssml, "strategy": "mstts"}

    ssml = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{_xml_escape(lang)}">'
        f'<voice name="{_xml_escape(voice)}">'
        f'<prosody rate="{_xml_escape(rate)}" pitch="{_xml_escape(pitch)}" volume="{_xml_escape(volume)}">'
        f"{body}"
        f"</prosody>"
        f"</voice>"
        f"</speak>"
    )
    return {"ssml": ssml, "strategy": "prosody_only"}


def render_ssml_with_fallback(
    text_raw: str,
    prosody: Dict[str, str],
    meta: Dict[str, Any],
    error_text: str,
    cfg: AzureSpeechConfig,
) -> Dict[str, Any]:
    flags = detect_ssml_unsupported(error_text)
    meta2 = dict(meta or {})
    if flags.get("drop_role"):
        meta2["role"] = None
    if flags.get("drop_style"):
        meta2["style"] = None
    if flags.get("drop_mstts"):
        meta2["use_mstts"] = False
    out = render_ssml(text_raw, prosody, meta2, cfg)
    out["fallback_flags"] = flags
    return out


def azure_tts_request(ssml_text: str, cfg: AzureSpeechConfig) -> bytes:
    key = _azure_speech_key(cfg)
    if not key:
        raise RuntimeError(f"{cfg.speech_key_env} is not set")
    region = _azure_region(cfg)
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": cfg.tts_output_format,
        "User-Agent": "aphrodite-runtime-tts",
    }
    data = (ssml_text or "").encode("utf-8")
    import urllib.request

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def azure_tts_synthesize(
    text_raw: str,
    prosody: Dict[str, str],
    meta: Optional[Dict[str, Any]] = None,
    cfg: Optional[AzureSpeechConfig] = None,
) -> Dict[str, Any]:
    c = cfg or load_azure_speech_config()
    m = dict(meta or {})
    pack = render_ssml(text_raw, prosody, m, c)
    try:
        audio = azure_tts_request(str(pack.get("ssml") or ""), c)
        return {"ok": True, "audio": audio, "render": pack}
    except Exception as e:
        err = str(e)
        try:
            if hasattr(e, "read"):
                err = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        fb = render_ssml_with_fallback(text_raw, prosody, m, err, c)
        try:
            audio = azure_tts_request(str(fb.get("ssml") or ""), c)
            return {"ok": True, "audio": audio, "render": fb}
        except Exception as e2:
            return {"ok": False, "error": str(e2), "render": fb}


def azure_stt_transcribe_wav(
    wav_path: str,
    language: Optional[str] = None,
    cfg: Optional[AzureSpeechConfig] = None,
) -> Dict[str, Any]:
    c = cfg or load_azure_speech_config()
    key = _azure_speech_key(c)
    if not key:
        return {"ok": False, "error": f"{c.speech_key_env} is not set"}
    region = _azure_region(c)
    lang = language or c.stt_language
    url = (
        f"https://{region}.stt.speech.microsoft.com/speech/recognition/"
        f"conversation/cognitiveservices/v1?language={lang}"
    )
    try:
        with open(wav_path, "rb") as f:
            data = f.read()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "audio/wav",
        "Accept": "application/json",
    }
    import urllib.request

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return {"ok": False, "error": str(e)}
    try:
        obj = json.loads(raw)
        return {"ok": True, "text": obj.get("DisplayText") or obj.get("Text") or "", "raw": obj}
    except Exception:
        return {"ok": True, "text": "", "raw": raw}


def ssml_prosody_from_state(emotion: str, energy: int, affinity: int) -> Dict[str, str]:
    try:
        e = int(energy)
    except Exception:
        e = 60
    try:
        a = int(affinity)
    except Exception:
        a = 20
    rate = 80 + int((max(0, min(100, e)) / 100.0) * 35)
    pitch = -2 + int((max(0, min(100, a)) / 100.0) * 4)
    emo = (emotion or "").lower()
    if emo in ("excited", "playful"):
        rate = min(120, rate + 6)
        pitch = min(3, pitch + 1)
    elif emo in ("sad", "tired"):
        rate = max(70, rate - 8)
        pitch = max(-3, pitch - 1)
    elif emo in ("worried",):
        rate = max(75, rate - 4)
    return {"rate": f"{rate}%", "pitch": f"{pitch}st"}


def save_wav(audio: bytes, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(audio)
    return path
