"""FastAPI backend for Maya — the local Nepanglish AI voice agent.

Exposes the AI pipeline (ASR -> LLM -> TTS) and the restaurant data (menu,
orders, call logs) as a small JSON API consumed by the Next.js frontend.

Run:  .venv\\Scripts\\python -m uvicorn backend.main:app --port 8000
"""
from __future__ import annotations

import base64
import json
import re
import sys
import threading
from pathlib import Path
from typing import Optional

# Make the `maya` package importable regardless of the launch cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from maya import db, llm
from maya.agent import Agent
from maya.config import DEFAULT_LLM_MODEL, RESTAURANT_NAME

app = FastAPI(title="Maya — Nepanglish AI Voice Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev: the Next.js frontend runs on :3000
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Shared engine (single agent; its model/voice can be changed at runtime)
# ---------------------------------------------------------------------------
db.init_db()
agent = Agent()


def _warmup_asr() -> None:
    """Preload the Whisper model so the first voice turn isn't slow."""
    try:
        from maya import asr as asr_mod

        asr_mod.load_model()
        print("[maya] ASR model warmed up")
    except Exception as exc:  # pragma: no cover
        print("[maya] ASR warmup failed:", exc)


def _warmup_llm() -> None:
    """Load the LLM into VRAM once and keep it loaded (no 20s reload per turn)."""
    try:
        llm.warmup(agent.model)
        print("[maya] LLM warmed up")
    except Exception as exc:  # pragma: no cover
        print("[maya] LLM warmup failed:", exc)


def _warmup_tts() -> None:
    """Load the local Piper voice once so the first reply speaks instantly."""
    try:
        from maya import tts as tts_mod

        tts_mod._load_piper()
        print("[maya] TTS (Piper) warmed up")
    except Exception as exc:  # pragma: no cover
        print("[maya] TTS warmup failed:", exc)


threading.Thread(target=_warmup_asr, daemon=True).start()
threading.Thread(target=_warmup_llm, daemon=True).start()
threading.Thread(target=_warmup_tts, daemon=True).start()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class OrderItem(BaseModel):
    menu_item_id: Optional[int] = None
    name: str
    qty: int
    price: float


class OrderCreate(BaseModel):
    phone: str = ""
    name: str = ""
    address: str = ""
    items: list[OrderItem]


class StatusUpdate(BaseModel):
    status: str


class SettingsUpdate(BaseModel):
    model: Optional[str] = None
    voice: Optional[str] = None
    restaurant: Optional[str] = None
    city: Optional[str] = None
    asr: Optional[str] = None
    provider: Optional[str] = None
    tts: Optional[str] = None


# ---------------------------------------------------------------------------
# Health / meta
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    from maya import asr as asr_mod
    from maya import tts as tts_mod

    return {
        "status": "ok",
        "ollama": llm.is_running(),
        "provider": llm.provider(),
        "tts": tts_mod.mode(),
        "model": agent.model,
        "voice": agent.voice,
        "asr_model": asr_mod.current_model(),
        "restaurant": agent.restaurant,
        "city": agent.city,
    }


@app.get("/api/models")
def models():
    return {"models": llm.list_models()}


@app.get("/api/greet")
def greet():
    text = agent.greeting()
    audio_b64, fmt = _speak_b64(text)
    return {"text": text, "audio_b64": audio_b64, "fmt": fmt}


# ---------------------------------------------------------------------------
# The voice turn: audio (and/or text) in -> transcript + reply + voice out
# ---------------------------------------------------------------------------
@app.post("/api/turn")
def turn(
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    history: Optional[str] = Form(None),
    order: Optional[str] = Form(None),
):
    transcript = (text or "").strip()

    # 1. ASR if audio was provided
    if audio is not None:
        data = audio.file.read()
        if data:
            try:
                transcript = agent.transcribe(data)
            except Exception as exc:  # pragma: no cover
                raise HTTPException(status_code=500, detail=f"ASR failed: {exc}")

    if not transcript:
        raise HTTPException(status_code=400, detail="No speech or text received.")

    # 2. Build conversation history (system prompt is added by the agent)
    try:
        history_msgs = json.loads(history) if history else []
    except json.JSONDecodeError:
        history_msgs = []
    prev_order = _parse_order_field(order)
    _inject_order(history_msgs, prev_order)
    history_msgs.append({"role": "user", "content": transcript})

    # 3. LLM response + authoritative order (from the <change> block)
    try:
        response = agent.respond_turn(transcript, history_msgs)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM failed: {exc}")

    clean, cart = agent.finalize(response, prev_order, transcript)

    # 4. TTS
    audio_b64, fmt = _speak_b64(clean) if clean else (None, "audio/wav")

    return {
        "transcript": transcript,
        "response": clean,
        "audio_b64": audio_b64,
        "fmt": fmt,
        "cart": cart,
    }


@app.post("/api/turn/stream")
def turn_stream(
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    history: Optional[str] = Form(None),
    order: Optional[str] = Form(None),
):
    """Streaming voice turn (NDJSON over a POST stream).

    Events: transcript -> token* -> audio* -> cart -> done.
    Sentence audio is synthesized as each sentence completes, so Maya starts
    speaking before the full reply is generated (low time-to-first-audio).
    """
    transcript = (text or "").strip()

    if audio is not None:
        data = audio.file.read()
        if data:
            try:
                transcript = agent.transcribe(data)
            except Exception as exc:  # pragma: no cover
                raise HTTPException(status_code=500, detail=f"ASR failed: {exc}")

    if not transcript:
        raise HTTPException(status_code=400, detail="No speech or text received.")

    try:
        history_msgs = json.loads(history) if history else []
    except json.JSONDecodeError:
        history_msgs = []
    prev_order = _parse_order_field(order)
    _inject_order(history_msgs, prev_order)
    history_msgs.append({"role": "user", "content": transcript})

    def gen():
        yield _sse({"type": "transcript", "text": transcript})

        try:
            tokens = agent.respond_turn_stream(transcript, history_msgs)
        except Exception as exc:
            yield _sse({"type": "error", "message": f"LLM failed: {exc}"})
            return

        parts: list[str] = []
        tts_buf = ""
        stopped = False
        for token in tokens:
            parts.append(token)
            if stopped:
                continue  # everything after <order> is the machine-only JSON

            tts_buf += token
            if "<change>" in tts_buf:
                idx = tts_buf.find("<change>")
                front = tts_buf[:idx].strip()
                if front:
                    b64, fmt = _speak_b64(front)
                    if b64:
                        yield _sse({"type": "audio", "b64": b64, "fmt": fmt})
                tts_buf = ""
                stopped = True
            else:
                stripped = tts_buf.strip()
                if len(stripped) > 4 and _SENT_END.search(stripped):
                    b64, fmt = _speak_b64(stripped)
                    if b64:
                        yield _sse({"type": "audio", "b64": b64, "fmt": fmt})
                    tts_buf = ""

        if tts_buf.strip():
            b64, fmt = _speak_b64(tts_buf.strip())
            if b64:
                yield _sse({"type": "audio", "b64": b64, "fmt": fmt})

        response = "".join(parts).strip()
        clean, cart = agent.finalize(response, prev_order, transcript)
        yield _sse({"type": "cart", "items": cart})
        yield _sse({"type": "done", "response": clean, "order": cart})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
@app.get("/api/menu")
def get_menu():
    return {"items": db.get_all_menu_items()}


@app.post("/api/menu")
def save_menu(payload: list[dict]):
    db.save_menu(payload)
    return {"ok": True, "count": len(db.get_all_menu_items())}


# ---------------------------------------------------------------------------
# Orders + call logs
# ---------------------------------------------------------------------------
@app.get("/api/orders")
def get_orders():
    return {"orders": db.get_orders()}


@app.post("/api/orders")
def create_order(payload: OrderCreate):
    items = [(i.menu_item_id, i.name, i.qty, i.price, "") for i in payload.items]
    if not items:
        raise HTTPException(status_code=400, detail="Order has no items.")
    order_id = db.create_order(payload.phone, payload.name, payload.address, items)
    db.log_call(payload.phone, summary=f"Order #{order_id} confirmed")
    return {"order_id": order_id}


@app.patch("/api/orders/{order_id}")
def update_order(order_id: int, payload: StatusUpdate):
    db.update_order_status(order_id, payload.status)
    return {"ok": True}


@app.get("/api/stats")
def stats():
    return db.get_order_stats()


@app.get("/api/calllogs")
def calllogs():
    return {"logs": db.get_call_logs()}


# ---------------------------------------------------------------------------
# Settings + TTS preview
# ---------------------------------------------------------------------------
@app.post("/api/settings")
def settings(payload: SettingsUpdate):
    if payload.model:
        agent.model = payload.model
    if payload.voice:
        agent.voice = payload.voice
    if payload.restaurant:
        agent.restaurant = payload.restaurant
    if payload.city:
        agent.city = payload.city
    if payload.provider:
        llm.set_provider(payload.provider)
    if payload.tts:
        from maya import tts as tts_mod

        tts_mod.set_mode(payload.tts)
        if payload.tts == "omnivoice":
            threading.Thread(target=tts_mod._load_omnivoice, daemon=True).start()
    if payload.asr:
        from maya import asr as asr_mod

        asr_mod.set_model(payload.asr)
        threading.Thread(target=asr_mod.load_model, daemon=True).start()
    return {"ok": True}


@app.post("/api/speak")
def speak(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text.")
    audio_b64, fmt = _speak_b64(text)
    return {"audio_b64": audio_b64, "fmt": fmt}


@app.post("/api/voice/reference")
def voice_reference(audio: UploadFile = File(...), text: str = Form("")):
    """Upload a short recording + its transcription to clone a voice."""
    from maya import tts as tts_mod

    data = audio.file.read()
    tts_mod.set_voice_reference(data, text)
    return {"ok": True, "cloned": bool(data)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SENT_END = re.compile(r"[.!?]$")


def _parse_order_field(order: Optional[str]) -> list:
    try:
        data = json.loads(order) if order else []
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _order_ctx(cart) -> str:
    if not cart:
        return "[] (empty)"
    return ", ".join(f"{c['qty']}x {c['name']}" for c in cart)


def _inject_order(history_msgs: list, prev_order: list) -> None:
    """Feed the LLM the current order so it maintains it across turns."""
    ctx = "Current order so far (respect this; the caller only changes what they say): " + _order_ctx(prev_order)
    history_msgs.insert(0, {"role": "system", "content": ctx})


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _speak_b64(text: str) -> tuple[Optional[str], str]:
    try:
        data, mime = agent.speak(text)
        return (base64.b64encode(data).decode("ascii"), mime) if data else (None, "audio/wav")
    except Exception:
        return (None, "audio/wav")
