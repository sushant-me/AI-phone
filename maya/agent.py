"""Orchestrator: turns the local ASR + LLM + TTS pieces into "Maya".

Also includes lightweight Nepanglish cart extraction so a live order panel can
be populated while the user talks, without needing fragile JSON output from the
LLM.
"""
from __future__ import annotations

import json
import re

from . import asr as asr_mod
from . import db, llm, prompts, tts as tts_mod
from .config import (
    AGENT_NAME,
    CITY,
    DEFAULT_LLM_MODEL,
    GREETING,
    RESTAURANT_NAME,
    TTS_VOICE,
)

# ---------------------------------------------------------------------------
# Nepanglish quantity parsing
# ---------------------------------------------------------------------------
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "a": 1, "an": 1, "single": 1,
    # Nepali / colloquial
    "euta": 1, "euta": 1, "ek": 1, "ekta": 1, "ekdam": 1,
    "dui": 2, "dwi": 2, "tin": 3, "teen": 3,
    "char": 4, "paanch": 5, "panch": 5, "pach": 5,
    "chha": 6, "cha": 6, "saat": 7, "sat": 7,
    "aath": 8, "ath": 8, "nau": 9, "das": 10, "dus": 10,
}
_TOKEN_RE = re.compile(r"\d+|[A-Za-z]+")


def _to_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token.lower())


def _qty_in_window(window: str) -> int | None:
    for tok in reversed(_TOKEN_RE.findall(window)):
        n = _to_number(tok)
        if n is not None and 1 <= n <= 50:
            return n
    return None


def extract_cart(text: str, menu_items: list[dict]) -> list[dict]:
    """Detect {name, qty, price, menu_item_id} entries in a Nepanglish utterance.

    Longest menu names are matched first and matched spans are claimed, so
    "Chicken Momo" is not double-counted as "Momo".
    """
    claimed: list[tuple[int, int]] = []
    found: dict[str, dict] = {}
    by_name = {m["name"].lower(): m for m in menu_items}

    for name in sorted(by_name, key=len, reverse=True):
        pattern = re.compile(re.escape(name) + r"(?:s|haru)?\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            s, e = match.span()
            if any(not (e <= cs or s >= ce) for cs, ce in claimed):
                continue  # already part of a longer matched item
            claimed.append((s, e))
            before = text[max(0, s - 40):s]
            qty = _qty_in_window(before)
            if qty is None:
                after = text[e:e + 12]
                qty = _qty_in_window(after) or 1
            item = by_name[name]
            if name in found:
                found[name]["qty"] += qty
            else:
                found[name] = {
                    "name": item["name"],
                    "qty": qty,
                    "price": item["price"],
                    "menu_item_id": item["id"],
                }
    return list(found.values())


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
class Agent:
    def __init__(
        self,
        model: str = DEFAULT_LLM_MODEL,
        voice: str = TTS_VOICE,
        restaurant: str = RESTAURANT_NAME,
        city: str = CITY,
    ):
        self.model = model
        self.voice = voice
        self.restaurant = restaurant
        self.city = city

    # -- menu / grounding ---------------------------------------------------
    def get_menu(self) -> list[dict]:
        return db.get_menu()

    def build_messages(self, history: list[dict]) -> list[dict]:
        sys_prompt = prompts.build_system_prompt(
            self.get_menu(), self.restaurant, self.city, AGENT_NAME
        )
        msgs = [{"role": "system", "content": sys_prompt}]
        for m in history:
            msgs.append({"role": m["role"], "content": m["content"]})
        return msgs

    # -- pipeline -----------------------------------------------------------
    def respond(self, history: list[dict]) -> str:
        return llm.chat(self.build_messages(history), model=self.model)

    def respond_stream(self, history: list[dict]):
        yield from llm.stream_chat(self.build_messages(history), model=self.model)

    def transcribe(self, audio_bytes: bytes) -> str:
        return asr_mod.transcribe(audio_bytes)

    def speak(self, text: str) -> tuple[bytes, str]:
        """Return (audio_bytes, mime) for the given text."""
        return tts_mod.synthesize(text)

    def detect_cart(self, text: str) -> list[dict]:
        return extract_cart(text, self.get_menu())

    def respond_turn(self, user_text: str, history: list[dict]) -> str:
        """Generate Maya's reply. Order changes are parsed from `<change>` tags."""
        return self.respond(history)

    def respond_turn_stream(self, user_text: str, history: list[dict]):
        """Streaming variant of respond_turn (yields tokens)."""
        return self.respond_stream(history)

    def finalize(
        self, response: str, prev_order: list[dict] | None = None, user_text: str = ""
    ) -> tuple[str, list[dict]]:
        """Apply the `<change>` delta to the previous order (authoritative state).

        The LLM only says what changed, and the backend keeps the real order, so
        items are never silently dropped. Removals are also matched by keyword so
        "remove / हटाउनु" always works.
        """
        prev_order = prev_order or []
        raw: list = []
        matched = _CHANGE_RE.search(response)
        if matched:
            try:
                parsed = json.loads(matched.group(1).strip())
                if isinstance(parsed, list):
                    raw = parsed
            except (json.JSONDecodeError, ValueError):
                raw = []

        clean = _CHANGE_TAG.sub("", response).strip()
        menu = self.get_menu()
        order = _apply_change(prev_order, raw, menu)
        if _REMOVE_WORDS.search(user_text):
            order = _apply_remove_intent(order, user_text, menu)
        if order:
            clean = _fix_total(clean, order)
        return clean, order

    def greeting(self) -> str:
        return GREETING


# ---------------------------------------------------------------------------
# Order delta application — the LLM outputs only <change>[...]</change> (items
# it added/updated/removed); the backend maintains the authoritative order.
# ---------------------------------------------------------------------------
_CHANGE_RE = re.compile(r"<change>(.*?)</change>", re.DOTALL | re.IGNORECASE)
_CHANGE_TAG = re.compile(r"<change>.*?</change>", re.DOTALL | re.IGNORECASE)
_REMOVE_WORDS = re.compile(r"remove|हटाउ|हटाय|हटाए|निकाल|निकाले|निकालेर|काढ", re.IGNORECASE)


def _match_menu_name(name: str, menu: dict) -> dict | None:
    mi = menu.get(name.lower())
    if mi is None:
        cands = [m for n, m in menu.items() if name.lower() in n or n in name.lower()]
        if len(cands) == 1:
            mi = cands[0]
    return mi


def _apply_remove_intent(order: list[dict], user_text: str, menu_items: list[dict]) -> list[dict]:
    """Drop any menu item named in a 'remove' message."""
    names = [m["name"] for m in menu_items]
    return [it for it in order if not re.search(re.escape(it["name"]), user_text, re.IGNORECASE)]


def _apply_change(prev_order: list[dict], raw: list, menu_items: list[dict]) -> list[dict]:
    menu = {m["name"].lower(): m for m in menu_items}
    order: dict[str, dict] = {}
    for it in prev_order:
        order[it["name"].lower()] = dict(it)

    for it in raw:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        mi = _match_menu_name(name, menu)
        if not mi:
            continue
        try:
            qty = int(it.get("qty") or 0)
        except (ValueError, TypeError):
            qty = 0
        qty = max(0, min(50, qty))
        key = mi["name"].lower()
        if qty == 0:
            order.pop(key, None)
        else:
            order[key] = {
                "name": mi["name"],
                "qty": qty,
                "price": mi["price"],
                "menu_item_id": mi["id"],
            }
    return list(order.values())


# ---------------------------------------------------------------------------
# Total correction — LLMs are unreliable at arithmetic, but our cart (exact)
# is authoritative. Replace "Total … rupees" with the correct figure.
# ---------------------------------------------------------------------------
_ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _num_to_words(n: int) -> str:
    if n == 0:
        return "zero"
    parts = []
    if n >= 1000:
        parts.append(f"{_ONES[n // 1000]} thousand")
        n %= 1000
    if n >= 100:
        parts.append(f"{_ONES[n // 100]} hundred")
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10])
        n %= 10
    if n > 0:
        parts.append(_ONES[n])
    return " ".join(parts)


_TOTAL_RE = re.compile(r"\b[Tt]otal\b[^,.;!?]*?\brupees?\b", re.IGNORECASE)


def _fix_total(text: str, cart: list[dict]) -> str:
    total = int(round(sum(c["qty"] * c["price"] for c in cart)))
    return _TOTAL_RE.sub(f"Total {_num_to_words(total)} rupees", text, count=1)
