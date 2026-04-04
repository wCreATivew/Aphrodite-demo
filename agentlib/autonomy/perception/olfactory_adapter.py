from __future__ import annotations

import time
from typing import Any, Dict, Optional


class OlfactoryAdapter:
    modality = "olfactory"

    def read(self, event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = dict(event or {"state_key": "air", "state_label": "normal"})
        return {
            "timestamp": float(payload.pop("timestamp", time.time())),
            "source": "mock_gas_sensor",
            "modality": self.modality,
            "payload": payload,
            "confidence": 0.73,
            "noise_level": 0.27,
        }
