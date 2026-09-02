"""Central configuration for the Maya voice agent."""
from __future__ import annotations

import os
from pathlib import Path


def _load_env() -> None:
    """Load a local `.env` file (KEY=VALUE lines) without extra dependencies."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "maya.db"

for _d in (DATA_DIR, AUDIO_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Restaurant identity (overridable from the Settings page at runtime)
# ---------------------------------------------------------------------------
RESTAURANT_NAME = "Everest Burger"
CITY = "Kathmandu"
AGENT_NAME = "Maya"
# Mixed Devanagari + English — spoken with correct Nepali pronunciation.
GREETING = "नमस्ते! Everest Burger मा Maya बोल्दै छु। के order गर्नु हुन्छ?"

# ---------------------------------------------------------------------------
# LLM — provider is "deepseek" (cloud, needs key; best conversation quality)
# or "ollama" (local, offline, zero-cost). The agent works with either.
# ---------------------------------------------------------------------------
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
LLM_PROVIDER = "deepseek" if DEEPSEEK_API_KEY else "ollama"

OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_LLM_MODEL = "qwen2.5:7b"      # Ollama fallback / local run
OLLAMA_KEEP_ALIVE = -1                # -1 = keep the model loaded in VRAM (no reload per turn)
LLM_TEMPERATURE = 0.4
LLM_TIMEOUT = 180                      # seconds

# ---------------------------------------------------------------------------
# ASR — faster-whisper, fully local (Silero VAD is enabled at transcribe time)
# ---------------------------------------------------------------------------
ASR_MODEL = "small"                    # small (fast) | base | medium | large-v3 (best)
ASR_LANGUAGE = None                    # None = auto-detect (handles ne + en mix)
ASR_DEVICE = "auto"                    # auto | cpu | cuda

# ---------------------------------------------------------------------------
# TTS — local Piper voice (fast, offline) with edge-tts fallback
# ---------------------------------------------------------------------------
PIPER_MODEL_PATH = str(BASE_DIR / "data" / "voices" / "ne_NP-google-medium.onnx")
TTS_VOICE = "ne-NP-HemkalaNeural"      # edge-tts fallback voice (needs internet)
TTS_RATE = "+0%"                       # natural conversational pace
TTS_PITCH = "+0Hz"
