"""Maya — a local "Nepanglish" AI voice agent for Nepalese restaurants.

A fully local conversational voice agent (per the project plan):
    mic / GSM audio -> VAD -> Whisper ASR -> Qwen LLM (menu-grounded) -> humanized TTS

Modules:
    config   — paths, identity, model/voice defaults
    db       — SQLite menu / orders / call-logs
    prompts  — the "Maya" system prompt + menu grounding (RAG)
    llm      — Ollama (local) chat client
    asr      — faster-whisper (local) speech-to-text
    tts      — edge-tts (humanized Nepali neural voice) + hooks for local engines
    agent    — orchestrator + Nepanglish cart extraction
"""

__version__ = "0.1.0"
