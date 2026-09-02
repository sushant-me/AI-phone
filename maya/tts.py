"""Text-to-speech.

Three engines:
  "natural"    — edge-tts (Microsoft neural voice, needs internet, fast)
  "local"      — Piper (offline, fast)
  "omnivoice"  — OmniVoice (k2-fsa): human multilingual TTS on GPU, supports
                 zero-shot voice cloning (set a reference voice and Maya speaks
                 in that voice). Nepali is `npi`.

Text is Devanagari Nepali + English so pronunciation is correct.
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import tempfile
import threading
import wave

import numpy as np

from .config import PIPER_MODEL_PATH, TTS_PITCH, TTS_RATE, TTS_VOICE

_mode = "natural"  # natural | local | omnivoice
_piper_voice = None
_omnivoice_model = None
_omnivoice_lock = threading.Lock()
_voice_ref = None  # (ref_audio_path, ref_text) for cloning

_MD_RE = re.compile(r"[*_#`>~\[\]]")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def set_mode(mode: str) -> None:
    global _mode
    if mode in ("natural", "local", "omnivoice"):
        _mode = mode


def mode() -> str:
    return _mode


def set_voice_reference(audio_bytes: bytes, text: str) -> None:
    """Set the voice to clone (reference audio + its transcription)."""
    global _voice_ref
    if not audio_bytes:
        _voice_ref = None
        return
    ref_dir = os.path.join(os.path.dirname(PIPER_MODEL_PATH), "..", "voices")
    os.makedirs(ref_dir, exist_ok=True)
    ref_path = os.path.join(ref_dir, "voice_ref.wav")
    with open(ref_path, "wb") as f:
        f.write(audio_bytes)
    _voice_ref = (ref_path, text.strip())


def _clean(text: str) -> str:
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_RE.sub("", text)
    text = text.replace("—", ", ").replace("–", ", ").replace("…", ", ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Piper (local)
# ---------------------------------------------------------------------------
def _load_piper():
    global _piper_voice
    if _piper_voice is None:
        from piper import PiperVoice

        _piper_voice = PiperVoice.load(PIPER_MODEL_PATH)
    return _piper_voice


def _wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sample_rate))
        w.writeframes(np.asarray(audio, dtype=np.int16).tobytes())
    return buf.getvalue()


def _piper_synth(text: str) -> bytes | None:
    try:
        voice = _load_piper()
        chunks = voice.synthesize(text)
        parts: list[np.ndarray] = []
        sample_rate: int | None = None
        for chunk in chunks:
            sample_rate = getattr(chunk, "sample_rate", sample_rate) or sample_rate
            int16_bytes = getattr(chunk, "audio_int16_bytes", None)
            if int16_bytes is not None:
                parts.append(np.frombuffer(int16_bytes, dtype=np.int16))
            else:
                f = np.asarray(getattr(chunk, "audio_float_array"), dtype=np.float32)
                parts.append((np.clip(f, -1, 1) * 32767).astype(np.int16))
        if parts and sample_rate:
            return _wav_bytes(np.concatenate(parts), sample_rate)
    except Exception as exc:  # pragma: no cover
        print("[tts] piper failed:", exc)
    return None


# ---------------------------------------------------------------------------
# OmniVoice (GPU, human, voice cloning)
# ---------------------------------------------------------------------------
def _load_omnivoice():
    global _omnivoice_model
    if _omnivoice_model is not None:
        return _omnivoice_model
    with _omnivoice_lock:
        if _omnivoice_model is not None:
            return _omnivoice_model
        import torch
        import transformers
        from transformers.models.higgs_audio_v2_tokenizer.modeling_higgs_audio_v2_tokenizer import (
            HiggsAudioV2TokenizerModel as _H,
        )

        transformers.HiggsAudioV2TokenizerModel = _H
        from omnivoice import OmniVoice

        _omnivoice_model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16
        )
    return _omnivoice_model


def _omnivoice_synth(text: str) -> bytes | None:
    try:
        model = _load_omnivoice()
        kwargs: dict = {"language": "npi"}
        if _voice_ref:
            kwargs["ref_audio"] = _voice_ref[0]
            kwargs["ref_text"] = _voice_ref[1]
        else:
            kwargs["instruct"] = "female"
        audio = model.generate(text, **kwargs)
        samples = np.asarray(audio[0], dtype=np.float32)
        int16 = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        return _wav_bytes(int16, 24000)
    except Exception as exc:  # pragma: no cover
        print("[tts] omnivoice failed:", exc)
        return None


# ---------------------------------------------------------------------------
# edge-tts (natural, cloud)
# ---------------------------------------------------------------------------
async def _edge_tts(text: str, voice: str, rate: str, pitch: str, out: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(out)


def _edge_tts_synth(text: str) -> bytes | None:
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            out = f.name
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_edge_tts(text, TTS_VOICE, TTS_RATE, TTS_PITCH, out))
            with open(out, "rb") as f:
                return f.read()
        finally:
            try:
                os.remove(out)
            except OSError:
                pass
            loop.close()
    except Exception as exc:  # pragma: no cover
        print("[tts] edge-tts failed:", exc)
        return None


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------
def synthesize(text: str) -> tuple[bytes, str]:
    """Return (audio_bytes, mime)."""
    text = _clean(text)
    if not text:
        return b"", "audio/wav"

    if _mode == "omnivoice":
        wav = _omnivoice_synth(text)
        if wav:
            return wav, "audio/wav"
    elif _mode == "local":
        wav = _piper_synth(text)
        if wav:
            return wav, "audio/wav"

    # natural / fallback
    mp3 = _edge_tts_synth(text)
    if mp3:
        return mp3, "audio/mpeg"
    wav = _piper_synth(text)
    if wav:
        return wav, "audio/wav"

    raise RuntimeError("no TTS engine available")
