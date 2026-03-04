from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


TEXT_EXTS = {".txt", ".md", ".markdown", ".json", ".jsonl", ".csv", ".log", ".srt", ".vtt"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


@dataclass
class DocChunk:
    source: str
    text: str
    chunk_id: str


def ingest_paths(
    paths: Sequence[str],
    *,
    chunk_size: int = 420,
    chunk_overlap: int = 80,
    enable_video_transcribe: bool = False,
) -> List[DocChunk]:
    files = _expand_paths(paths)
    out: List[DocChunk] = []
    for fp in files:
        suffix = fp.suffix.lower()
        if suffix in TEXT_EXTS:
            text = _read_text_file(fp)
        elif suffix in VIDEO_EXTS:
            text = _read_video_text(fp, enable_video_transcribe=enable_video_transcribe)
        else:
            continue

        text = _normalize_text(text)
        if not text:
            continue
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
        for i, c in enumerate(chunks):
            out.append(DocChunk(source=str(fp), text=c, chunk_id=f"{fp.name}#{i+1}"))
    return out


def chunk_text(text: str, *, chunk_size: int = 420, overlap: int = 80) -> List[str]:
    t = str(text or "").strip()
    if not t:
        return []
    size = max(80, int(chunk_size))
    ov = max(0, min(int(overlap), size // 2))
    if len(t) <= size:
        return [t]

    out: List[str] = []
    i = 0
    step = max(1, size - ov)
    while i < len(t):
        part = t[i : i + size].strip()
        if part:
            out.append(part)
        i += step
    return out


def _expand_paths(paths: Sequence[str]) -> List[Path]:
    out: List[Path] = []
    for p in paths:
        path = Path(str(p)).expanduser().resolve()
        if path.is_file():
            out.append(path)
            continue
        if path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    out.append(f.resolve())
    # stable order for reproducibility
    out = sorted(set(out), key=lambda x: str(x))
    return out


def _read_text_file(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return path.read_text(encoding=enc, errors="ignore")
        except Exception:
            continue
    return ""


def _read_video_text(path: Path, *, enable_video_transcribe: bool) -> str:
    # 1) try sidecar transcript first
    sidecars = [
        path.with_suffix(".srt"),
        path.with_suffix(".vtt"),
        path.with_suffix(".txt"),
        path.with_name(path.stem + ".transcript.txt"),
    ]
    for sc in sidecars:
        if sc.exists() and sc.is_file():
            return _read_text_file(sc)

    # 2) optional local whisper transcription
    if enable_video_transcribe:
        txt = _transcribe_with_whisper(path)
        if txt:
            return txt

    return ""


def _transcribe_with_whisper(path: Path) -> str:
    try:
        import whisper  # type: ignore
    except Exception:
        return ""
    try:
        model = whisper.load_model("base")
        result: Dict[str, str] = model.transcribe(str(path), fp16=False)
        return str(result.get("text", "")).strip()
    except Exception:
        return ""


def _normalize_text(text: str) -> str:
    t = str(text or "")
    # remove common subtitle markers
    t = re.sub(r"^\d+\s*$", "", t, flags=re.M)
    t = re.sub(
        r"\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}",
        "",
        t,
    )
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
