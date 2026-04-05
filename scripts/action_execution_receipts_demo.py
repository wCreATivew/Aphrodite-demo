from __future__ import annotations

import json
import os
import time
from dataclasses import asdict

from agentlib.autonomy.actuation import ActionEnvelope, DialogueExecutor, InteractionExecutor


def run_demo() -> list[dict]:
    records = []

    ok_executor = InteractionExecutor(action_sink=lambda payload: {"echo": payload.get("payload", {})})
    ok_receipt = ok_executor.execute(
        ActionEnvelope.build(
            channel="interaction_feedback",
            target="ui",
            payload={"text": "all-good"},
            retry_policy={"max_attempts": 2, "idempotent": True, "base_delay_ms": 10},
        )
    )
    records.append({"case": "success", "receipt": asdict(ok_receipt)})

    fail_executor = InteractionExecutor(action_sink=lambda _payload: (_ for _ in ()).throw(RuntimeError("boom")))
    fail_receipt = fail_executor.execute(
        ActionEnvelope.build(
            channel="interaction_feedback",
            target="ui",
            payload={"text": "will-fail"},
            retry_policy={"max_attempts": 1, "idempotent": False},
        )
    )
    records.append({"case": "fail", "receipt": asdict(fail_receipt)})

    def slow_text_sink(_text: str, _payload: dict) -> None:
        time.sleep(0.05)

    timeout_executor = DialogueExecutor(text_sink=slow_text_sink)
    timeout_receipt = timeout_executor.execute(
        ActionEnvelope.build(
            channel="dialog_utterance",
            target="user",
            payload={"text": "slow-message"},
            timeout_s=0.001,
            retry_policy={"max_attempts": 1, "idempotent": True},
        )
    )
    records.append({"case": "timeout", "receipt": asdict(timeout_receipt)})

    return records


def main() -> None:
    records = run_demo()
    os.makedirs("reports", exist_ok=True)
    output = "reports/action_execution_records.jsonl"
    with open(output, "w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(output)


if __name__ == "__main__":
    main()
