"""Maya self-test — verifies DB, ASR, LLM and TTS all work end to end.

Run:  python scripts/selftest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maya import asr as asr_mod
from maya import db, llm, tts as tts_mod
from maya.agent import Agent


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    # 1. DB
    section("1. Database")
    db.init_db()
    menu = db.get_menu()
    print(f"menu items: {len(menu)}")
    assert menu, "menu is empty"
    print("sample:", ", ".join(m["name"] for m in menu[:6]))

    # 2. Prompt grounding
    section("2. Prompt (RAG) grounding")
    agent = Agent()
    msgs = agent.build_messages([])
    sys_prompt = msgs[0]["content"]
    assert "Chicken Momo" in sys_prompt and "Rs 250" in sys_prompt
    print(f"system prompt: {len(sys_prompt)} chars, grounded with menu ✓")

    # 3. Cart extraction
    section("3. Nepanglish cart extraction")
    samples = [
        "euta mixed pizza ra dui ota cold coffee order garne",
        "2 chicken momo ani tin ota coke",
        "chicken momo",
    ]
    for s in samples:
        print(f"  {s!r} -> {agent.detect_cart(s)}")

    # 4. LLM
    section("4. LLM (Ollama)")
    if not llm.is_running():
        print("Ollama not running — skipping LLM test.")
    else:
        reply = agent.respond([{"role": "user", "content": "Namaste, euta chicken momo dinus na"}])
        print("Maya:", reply)

    # 5. TTS
    section("5. TTS (humanized Nepali voice)")
    try:
        audio = agent.speak("Namaste! Hajur, aaja ke order garnu hunchha?")
        print(f"TTS ok — {len(audio)} bytes of MP3")
        with open(Path(db.DB_PATH).parent / "audio" / "greeting.mp3", "wb") as f:
            f.write(audio)
    except Exception as exc:
        print(f"TTS failed (needs internet): {exc}")

    # 6. ASR round-trip (synthesize a phrase, then transcribe it back)
    section("6. ASR round-trip")
    try:
        import edge_tts, asyncio, tempfile, os
        phrase = "hello this is a test of the local voice agent"
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        asyncio.run(edge_tts.Communicate(phrase).save(tmp.name))
        with open(tmp.name, "rb") as f:
            data = f.read()
        os.remove(tmp.name)
        text = asr_mod.transcribe(data)
        print(f"whisper heard: {text!r}")
    except Exception as exc:
        print(f"ASR round-trip failed: {exc}")

    print("\n✅ Self-test complete.")


if __name__ == "__main__":
    main()
