"""End-to-end pipeline test: TTS -> LLM -> ASR.

Run:  .venv\\Scripts\\python scripts/pipeline_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maya import db, llm
from maya.agent import Agent

AUDIO = Path(__file__).resolve().parent.parent / "data" / "audio"


def main() -> None:
    db.init_db()
    agent = Agent()

    print("=== 1. Menu ===")
    menu = agent.get_menu()
    print(f"{len(menu)} items. Sample:", ", ".join(m["name"] for m in menu[:5]))

    print("\n=== 2. TTS (humanized Nepali voice) ===")
    phrase = "Namaste! Hajur, aaja ke order garnu hunchha?"
    try:
        mp3 = agent.speak(phrase)
        (AUDIO / "pipeline_greeting.mp3").write_bytes(mp3)
        print(f"OK — {len(mp3)} bytes -> data/audio/pipeline_greeting.mp3")
    except Exception as exc:
        print(f"TTS FAILED (needs internet): {exc}")

    print("\n=== 3. LLM (Qwen2.5 via Ollama) ===")
    if not llm.is_running():
        print("Ollama not running — skipping.")
    else:
        reply = agent.respond(
            [{"role": "user", "content": "Namaste, euta chicken momo ra dui ota cold coffee order garne"}]
        )
        print("Maya:", reply)

    print("\n=== 4. ASR (faster-whisper, medium, Silero VAD) ===")
    wav = AUDIO / "asr_test.wav"
    if not wav.exists():
        print("No test wav — skipping.")
    else:
        try:
            text = agent.transcribe(wav.read_bytes())
            print("Whisper heard:", repr(text))
        except Exception as exc:
            print(f"ASR FAILED: {exc}")

    print("\nDone.")


if __name__ == "__main__":
    main()
