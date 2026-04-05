from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


UnifiedPerception = Dict[str, Any]


@dataclass
class FusionConfig:
    alignment_window_sec: float = 1.5
    conflict_penalty: float = 0.25
    required_modalities: Tuple[str, ...] = ("vision", "audio", "tactile", "olfactory")
    modality_priority: Tuple[str, ...] = ("vision", "tactile", "audio", "olfactory")


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
                "degradation_mode": "all_missing",
                "arbitration_log": [],
                "brain_signal": {
                    "confidence": 0.0,
                    "uncertainty": 1.0,
                    "uncertainty_label": "critical",
                },
            }

        cleaned.sort(key=lambda item: float(item["timestamp"]))
        aligned = self._align(cleaned)
        conflicts, summary, arbitration_log = self._adjudicate_states(aligned)
        degradation_mode = self._degradation_mode(aligned)
        brain_signal = self._brain_signal(summary)
        return {
            "timestamp": time.time(),
            "aligned_events": aligned,
            "modality_status": self._modality_status(cleaned),
            "conflicts": conflicts,
            "summary": summary,
            "degraded": degradation_mode != "full",
            "degradation_mode": degradation_mode,
            "arbitration_log": arbitration_log,
            "brain_signal": brain_signal,
        }

    def _normalize_frame(self, frame: Mapping[str, Any]) -> UnifiedPerception:
        modality = self._canonical_modality(str(frame.get("modality", "unknown")))
        return {
            "timestamp": float(frame.get("timestamp", time.time())),
            "source": str(frame.get("source", "unknown")),
            "modality": modality,
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

    def _canonical_modality(self, modality: str) -> str:
        normalized = str(modality or "").strip().lower()
        aliases = {
            "visual": "vision",
            "vision": "vision",
            "audio": "audio",
            "auditory": "audio",
            "touch": "tactile",
            "tactile": "tactile",
            "haptic": "tactile",
            "olfactory": "olfactory",
            "smell": "olfactory",
        }
        return aliases.get(normalized, normalized or "unknown")

    def _modality_rank(self, modality: str) -> int:
        try:
            return self.config.modality_priority.index(modality)
        except ValueError:
            return len(self.config.modality_priority)

    def _adjudicate_states(
        self, frames: List[UnifiedPerception]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
        by_key: Dict[str, List[UnifiedPerception]] = {}
        for frame in frames:
            key = str(frame["payload"].get("state_key", frame["modality"]))
            by_key.setdefault(key, []).append(frame)

        conflicts: List[Dict[str, Any]] = []
        summary: Dict[str, Dict[str, Any]] = {}
        arbitration_log: List[Dict[str, Any]] = []

        for state_key, state_frames in by_key.items():
            labels = {str(i["payload"].get("state_label", "unknown")) for i in state_frames}
            ranked = sorted(
                state_frames,
                key=lambda item: (
                    self._modality_rank(str(item["modality"])),
                    -float(item["confidence"]),
                    float(item["noise_level"]),
                ),
            )
            winner = ranked[0]
            conflict_exists = len(labels) > 1
            if conflict_exists:
                conflicts.append(
                    {
                        "state_key": state_key,
                        "labels": sorted(labels),
                        "modalities": sorted({str(i["modality"]) for i in state_frames}),
                        "winner_modality": winner["modality"],
                        "winner_label": winner["payload"].get("state_label"),
                    }
                )
                for frame in state_frames:
                    if frame is winner:
                        continue
                    confidence = float(frame.get("confidence", 0.0))
                    frame["confidence"] = max(0.0, round(confidence - self.config.conflict_penalty, 3))

            winner_confidence = float(winner.get("confidence", 0.0))
            uncertainty = round(1.0 - winner_confidence, 3)
            uncertainty_label = self._uncertainty_label(uncertainty)
            summary[state_key] = {
                "state_label": winner["payload"].get("state_label"),
                "best_modality": winner["modality"],
                "confidence": winner_confidence,
                "uncertainty": uncertainty,
                "uncertainty_label": uncertainty_label,
                "evidence_modalities": sorted({str(i["modality"]) for i in state_frames}),
            }
            arbitration_log.append(
                {
                    "state_key": state_key,
                    "decision": winner["payload"].get("state_label"),
                    "winner_modality": winner["modality"],
                    "reason": "priority_rule" if conflict_exists else "single_label",
                    "conflict": conflict_exists,
                    "candidates": [
                        {
                            "modality": i["modality"],
                            "label": i["payload"].get("state_label"),
                            "confidence": i["confidence"],
                            "noise_level": i["noise_level"],
                        }
                        for i in state_frames
                    ],
                }
            )
        return conflicts, summary, arbitration_log

    def _degradation_mode(self, frames: List[UnifiedPerception]) -> str:
        available = {str(frame["modality"]) for frame in frames}
        required = set(self.config.required_modalities)
        if not available:
            return "all_missing"
        missing = required - available
        if not missing:
            return "full"
        if len(missing) == 1:
            return "single_missing"
        return "double_or_more_missing"

    def _uncertainty_label(self, uncertainty: float) -> str:
        if uncertainty <= 0.2:
            return "low"
        if uncertainty <= 0.45:
            return "medium"
        if uncertainty <= 0.7:
            return "high"
        return "critical"

    def _brain_signal(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        if not summary:
            return {"confidence": 0.0, "uncertainty": 1.0, "uncertainty_label": "critical"}
        confidences = [float(item.get("confidence", 0.0)) for item in summary.values()]
        confidence = round(sum(confidences) / max(1, len(confidences)), 3)
        uncertainty = round(1.0 - confidence, 3)
        return {
            "confidence": confidence,
            "uncertainty": uncertainty,
            "uncertainty_label": self._uncertainty_label(uncertainty),
        }
