from __future__ import annotations

import time
from typing import Any, Dict, Optional


class VisionAdapter:
    modality = "vision"

    def read(self, event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = dict(event or {"state_key": "door", "state_label": "open"})
        return {
            "timestamp": float(payload.pop("timestamp", time.time())),
            "source": "mock_camera",
            "modality": self.modality,
            "payload": payload,
            "confidence": 0.88,
            "noise_level": 0.12,
        }
