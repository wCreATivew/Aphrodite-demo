from __future__ import annotations

import time
from typing import Any, Dict, Optional


class TactileAdapter:
    modality = "tactile"

    def read(self, event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = dict(event or {"state_key": "door", "state_label": "blocked"})
        return {
            "timestamp": float(payload.pop("timestamp", time.time())),
            "source": "mock_force_sensor",
            "modality": self.modality,
            "payload": payload,
            "confidence": 0.86,
            "noise_level": 0.18,
        }
