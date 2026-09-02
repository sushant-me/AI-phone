"""Speech-to-text via faster-whisper (fully local, GPU-accelerated).

faster-whisper runs Whisper through CTranslate2 and ships a built-in Silero VAD
(`vad_filter=True`), so we get the plan's "Silero VAD -> Whisper" pipeline in one
local call.

On this machine PyAV (`av`) is blocked by a Windows Application-Control policy,
so we decode WAV ourselves with `soundfile` and hand faster-whisper a raw NumPy
array (it only uses PyAV when given a file path). A minimal `av` stub is injected
so the package can still be imported.
"""
from __future__ import annotations

import io
import sys
import threading
import types

import numpy as np
import soundfile as sf

from .config import ASR_DEVICE, ASR_LANGUAGE, ASR_MODEL

_model = None
_model_size = ASR_MODEL
_load_lock = threading.Lock()


def current_model() -> str:
    return _model_size


def set_model(size: str) -> None:
    """Switch the Whisper model size at runtime (reloads lazily on next use)."""
    global _model, _model_size
    if size and size != _model_size:
        _model_size = size
        _model = None


def _ensure_av_importable() -> None:
    """If PyAV is blocked, inject a stub so `import faster_whisper` still works.

    The stub is never actually used — we always pass a NumPy array to
    `WhisperModel.transcribe()`, which skips `decode_audio` entirely.
    """
    if "av" in sys.modules:
        return
    try:
        import av  # noqa: F401
        return  # PyAV works, no stub needed
    except Exception:
        pass

    stub = types.ModuleType("av")

    class _Error:
        class InvalidDataError(Exception):
            pass

    stub.error = _Error
    sys.modules["av"] = stub


def _cuda_runtime_available() -> bool:
    """True only if the CUDA runtime (cublas) is actually loadable.

    ctranslate2 bundles cuDNN but not the CUDA runtime, so `device="cuda"`
    fails lazily at encode time with "cublas64_12.dll not found" when the
    NVIDIA driver is present but the CUDA toolkit is not installed.
    """
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        ctypes.WinDLL("cublas64_12.dll")
        return True
    except OSError:
        return False


def _device_attempts() -> list[tuple[str, str]]:
    """Ordered (device, compute_type) attempts, per ASR_DEVICE."""
    if ASR_DEVICE == "cpu":
        return [("cpu", "int8")]
    if ASR_DEVICE == "cuda":
        return [("cuda", "float16")]
    if _cuda_runtime_available():
        return [("cuda", "float16"), ("cpu", "int8")]
    return [("cpu", "int8")]


def load_model():
    global _model
    if _model is not None:
        return _model
    with _load_lock:
        if _model is not None:
            return _model
        _ensure_av_importable()
        from faster_whisper import WhisperModel

        last_exc: Exception | None = None
        for device, compute_type in _device_attempts():
            try:
                _model = WhisperModel(_model_size, device=device, compute_type=compute_type)
                return _model
            except Exception as exc:  # e.g. missing cublas -> fall back to CPU
                last_exc = exc
                _model = None
        raise last_exc or RuntimeError("failed to load the Whisper model")


def _decode_wav(audio_bytes: bytes) -> np.ndarray:
    """Decode WAV bytes to a 16 kHz mono float32 array (no PyAV / ffmpeg)."""
    audio, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # stereo -> mono
    if sr != 16000:
        duration = len(audio) / sr
        n_out = int(round(duration * 16000))
        x_old = np.linspace(0.0, len(audio) - 1.0, num=len(audio))
        x_new = np.linspace(0.0, len(audio) - 1.0, num=n_out)
        audio = np.interp(x_new, x_old, audio).astype(np.float32)
    return audio.astype(np.float32)


def transcribe(audio_bytes: bytes, language: str | None = None) -> str:
    """Transcribe WAV bytes to text. `language=None` auto-detects Nepali + English."""
    model = load_model()
    audio = _decode_wav(audio_bytes)
    segments, _info = model.transcribe(
        audio,
        language=language or ASR_LANGUAGE,
        vad_filter=True,       # Silero VAD — ignores traffic/kitchen noise
        beam_size=5,
        condition_on_previous_text=False,
    )
    return " ".join(s.text.strip() for s in segments).strip()
