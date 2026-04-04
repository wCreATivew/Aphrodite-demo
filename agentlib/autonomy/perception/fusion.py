from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional


UnifiedPerception = Dict[str, Any]


@dataclass
class FusionConfig:
    alignment_window_sec: float = 1.5
    conflict_penalty: float = 0.25


class PerceptionFusionEngine:
    """Align multi-modal events and resolve simple semantic conflicts.

    Missing modalities are expected and treated as degraded-input mode.
    """

    def __init__(self, config: Optional[FusionConfig] = None) -> None:
        self.config = config or FusionConfig()

    def run_cycle(self, frames: Iterable[UnifiedPerception]) -> Dict[str, Any]:
        cleaned = [self._normalize_frame(frame) for frame in frames if frame]
        if not cleaned:
            now = time.time()
            return {
                "timestamp": now,
                "aligned_events": [],
                "modality_status": {},
                "conflicts": [],
                "summary": {},
                "degraded": True,
            }

        cleaned.sort(key=lambda item: float(item["timestamp"]))
        aligned = self._align(cleaned)
        conflicts = self._detect_conflicts(aligned)
        self._apply_conflict_penalty(aligned, conflicts)
        return {
            "timestamp": time.time(),
            "aligned_events": aligned,
            "modality_status": self._modality_status(cleaned),
            "conflicts": conflicts,
            "summary": self._summarize(aligned),
            "degraded": False,
        }

    def _normalize_frame(self, frame: Mapping[str, Any]) -> UnifiedPerception:
        return {
            "timestamp": float(frame.get("timestamp", time.time())),
            "source": str(frame.get("source", "unknown")),
            "modality": str(frame.get("modality", "unknown")),
            "payload": dict(frame.get("payload", {}) or {}),
            "confidence": float(frame.get("confidence", 0.0)),
            "noise_level": float(frame.get("noise_level", 1.0)),
        }

    def _align(self, frames: List[UnifiedPerception]) -> List[UnifiedPerception]:
        if not frames:
            return []
        base_ts = min(float(item["timestamp"]) for item in frames)
        for item in frames:
            item["aligned_offset"] = round(float(item["timestamp"]) - base_ts, 3)
            item["within_window"] = item["aligned_offset"] <= self.config.alignment_window_sec
        return frames

    def _modality_status(self, frames: List[UnifiedPerception]) -> Dict[str, Dict[str, Any]]:
        status: Dict[str, Dict[str, Any]] = {}
        for item in frames:
            modality = str(item["modality"])
            status[modality] = {
                "present": True,
                "source": item["source"],
                "confidence": item["confidence"],
                "noise_level": item["noise_level"],
            }
        return status

    def _detect_conflicts(self, frames: List[UnifiedPerception]) -> List[Dict[str, Any]]:
        by_key: Dict[str, List[UnifiedPerception]] = {}
        for frame in frames:
            key = str(frame["payload"].get("state_key", ""))
            if not key:
                continue
            by_key.setdefault(key, []).append(frame)

        conflicts: List[Dict[str, Any]] = []
        for state_key, items in by_key.items():
            labels = {str(i["payload"].get("state_label", "unknown")) for i in items}
            if len(labels) > 1:
                conflicts.append(
                    {
                        "state_key": state_key,
                        "labels": sorted(labels),
                        "modalities": sorted({str(i["modality"]) for i in items}),
                    }
                )
        return conflicts

    def _apply_conflict_penalty(self, frames: List[UnifiedPerception], conflicts: List[Dict[str, Any]]) -> None:
        if not conflicts:
            return
        conflict_keys = {str(item["state_key"]) for item in conflicts}
        for frame in frames:
            state_key = str(frame["payload"].get("state_key", ""))
            if state_key in conflict_keys:
                confidence = float(frame.get("confidence", 0.0))
                frame["confidence"] = max(0.0, round(confidence - self.config.conflict_penalty, 3))

    def _summarize(self, frames: List[UnifiedPerception]) -> Dict[str, Any]:
        summary: Dict[str, Dict[str, Any]] = {}
        for frame in frames:
            key = str(frame["payload"].get("state_key", frame["modality"]))
            summary[key] = {
                "state_label": frame["payload"].get("state_label"),
                "best_modality": frame["modality"],
                "confidence": frame["confidence"],
            }
        return summary
