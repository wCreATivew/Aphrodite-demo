from __future__ import annotations

import time
from typing import Any, Dict, Optional


class AudioAdapter:
    modality = "audio"

    def read(self, event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = dict(event or {"state_key": "room", "state_label": "quiet"})
        return {
            "timestamp": float(payload.pop("timestamp", time.time())),
            "source": "mock_microphone",
            "modality": self.modality,
            "payload": payload,
            "confidence": 0.81,
            "noise_level": 0.2,
        }
