"""LLM client — DeepSeek (cloud, OpenAI-compatible) and Ollama (local).

Provider is switched at runtime via `set_provider("deepseek" | "ollama")`.
"""
from __future__ import annotations

import json
from typing import Iterator

import requests

from .config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEFAULT_LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
    LLM_PROVIDER,
    OLLAMA_HOST,
    OLLAMA_KEEP_ALIVE,
)

_provider = LLM_PROVIDER


def set_provider(name: str) -> None:
    global _provider
    if name in ("deepseek", "ollama"):
        _provider = name


def provider() -> str:
    return _provider


def is_running() -> bool:
    if provider() == "deepseek":
        return bool(DEEPSEEK_API_KEY)
    try:
        requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def list_models() -> list[str]:
    if provider() == "deepseek":
        return [DEEPSEEK_MODEL, "deepseek-reasoner"]
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))
    except Exception:
        return []


def warmup(model: str = DEFAULT_LLM_MODEL) -> None:
    """Preload whatever the active provider needs."""
    try:
        if provider() == "deepseek":
            chat([{"role": "user", "content": "hi"}], model=DEEPSEEK_MODEL, temperature=0)
        else:
            chat([{"role": "user", "content": "hi"}], model=model, temperature=0)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# DeepSeek (OpenAI-compatible)
# ---------------------------------------------------------------------------
def _deepseek(messages, stream: bool) -> Iterator[str] | str:
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": LLM_TEMPERATURE,
        "stream": stream,
    }
    r = requests.post(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        stream=stream,
        timeout=(10, 60),  # connect 10s, read 60s — avoid infinite hangs
    )
    r.raise_for_status()

    if not stream:
        return r.json()["choices"][0]["message"]["content"].strip()

    def gen():
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if delta:
                yield delta
            if data.get("choices", [{}])[0].get("finish_reason"):
                break

    return gen()


# ---------------------------------------------------------------------------
# Ollama (local)
# ---------------------------------------------------------------------------
def _ollama_payload(messages, model, temperature):
    return {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"temperature": temperature},
    }


def _ollama(messages, model, stream: bool) -> Iterator[str] | str:
    payload = _ollama_payload(messages, model, LLM_TEMPERATURE)
    if stream:
        payload["stream"] = True
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, stream=True, timeout=LLM_TIMEOUT)
        r.raise_for_status()

        def gen():
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = data.get("message", {}).get("content", "")
                if delta:
                    yield delta
                if data.get("done"):
                    break

        return gen()

    r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=LLM_TIMEOUT)
    r.raise_for_status()
    return (r.json().get("message", {}).get("content") or "").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def chat(messages, model: str = DEFAULT_LLM_MODEL, temperature: float = LLM_TEMPERATURE) -> str:
    if provider() == "deepseek":
        try:
            return _deepseek(messages, stream=False)  # type: ignore[return-value]
        except Exception as exc:
            print("[llm] deepseek failed, falling back to ollama:", exc)
    return _ollama(messages, model, stream=False)  # type: ignore[return-value]


def stream_chat(
    messages, model: str = DEFAULT_LLM_MODEL, temperature: float = LLM_TEMPERATURE
) -> Iterator[str]:
    if provider() == "deepseek":
        try:
            gen = _deepseek(messages, stream=True)  # type: ignore[arg-type]
            first = next(gen)  # trigger the POST (raises on connect failure)
            yield first
            yield from gen
            return
        except Exception as exc:
            print("[llm] deepseek failed, falling back to ollama:", exc)
    yield from _ollama(messages, model, stream=True)  # type: ignore[arg-type]
