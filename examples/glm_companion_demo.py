from __future__ import annotations

from agentlib.companion_chat import companion_reply_stream


def main() -> int:
    print("GLM5 Companion Demo (empty input to exit)")
    history = []
    while True:
        user_text = input("\nYou: ").strip()
        if not user_text:
            print("Bye.")
            return 0

        print("Assistant: ", end="", flush=True)
        chunks = []
        for piece in companion_reply_stream(user_text=user_text, history=history):
            chunks.append(piece)
            print(piece, end="", flush=True)
        print()

        assistant_text = "".join(chunks).strip()
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": assistant_text})


if __name__ == "__main__":
    raise SystemExit(main())
