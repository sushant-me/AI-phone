"""SQLite persistence: menu, orders, order-items and call logs.

Matches the plan's "SQLite stores menu items, prices, and call logs locally as a
single file" requirement — zero external database server.
"""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime

from .config import DB_PATH


def _int_id(v) -> int | None:
    """Coerce a possibly-NaN id (from st.data_editor) to int or None."""
    try:
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
        return int(v)
    except (ValueError, TypeError):
        return None

SCHEMA = """
CREATE TABLE IF NOT EXISTS menu_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'Main',
    price       REAL    NOT NULL,
    description TEXT    DEFAULT '',
    available   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phone         TEXT,
    customer_name TEXT,
    address       TEXT,
    total         REAL    NOT NULL DEFAULT 0,
    status        TEXT    NOT NULL DEFAULT 'New',
    notes         TEXT    DEFAULT '',
    created_at    TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       INTEGER NOT NULL,
    menu_item_id   INTEGER,
    item_name      TEXT    NOT NULL,
    qty            INTEGER NOT NULL,
    unit_price     REAL    NOT NULL,
    customizations TEXT    DEFAULT ''
);
CREATE TABLE IF NOT EXISTS call_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phone       TEXT,
    direction   TEXT    NOT NULL DEFAULT 'inbound',
    summary     TEXT,
    started_at  TEXT    NOT NULL,
    duration_s  REAL    DEFAULT 0
);
"""

# (name, category, price, description) — an authentic Kathmandu menu.
SEED_MENU = [
    ("Chicken Momo", "Momo", 250, "Steamed dumplings with chicken, 10 pcs"),
    ("Buff Momo", "Momo", 220, "Steamed dumplings with buffalo, 10 pcs"),
    ("Veg Momo", "Momo", 180, "Steamed dumplings with vegetables, 10 pcs"),
    ("Jhol Momo", "Momo", 260, "Momo in a spicy tangy soup"),
    ("Fried Momo", "Momo", 270, "Crispy fried dumplings, 10 pcs"),
    ("Kothey Momo", "Momo", 280, "Pan-fried dumplings, half steamed half crispy"),
    ("Chicken Chowmein", "Main", 200, "Stir-fried noodles with chicken"),
    ("Buff Chowmein", "Main", 180, "Stir-fried noodles with buffalo"),
    ("Chicken Thukpa", "Main", 220, "Nepali noodle soup with chicken"),
    ("Thenthuk", "Main", 230, "Hand-pulled Tibetan noodle soup"),
    ("Dal Bhat", "Main", 350, "Lentil soup, rice, vegetables and pickle"),
    ("Chicken Biryani", "Main", 320, "Fragrant spiced rice with chicken"),
    ("Choila", "Newari", 350, "Spiced grilled buffalo, Newari style"),
    ("Chicken Sekuwa", "Newari", 380, "Charcoal-grilled marinated chicken"),
    ("Chatamari", "Newari", 250, "Newari rice crepe with toppings"),
    ("Samay Baji", "Newari", 300, "Traditional Newari platter"),
    ("Bara", "Newari", 150, "Lentil patty, Newari style"),
    ("Mixed Pizza", "Fast Food", 550, "Medium pizza with mixed toppings"),
    ("Everest Burger", "Fast Food", 380, "Signature beef burger with fries"),
    ("Chicken Burger", "Fast Food", 320, "Crispy chicken burger"),
    ("French Fries", "Fast Food", 150, "Golden fried potato fries"),
    ("Wai Wai Sadeko", "Snacks", 80, "Spicy crunchy noodle chaat"),
    ("Cold Coffee", "Drinks", 180, "Chilled creamy coffee"),
    ("Masala Tea", "Drinks", 60, "Nepali spiced milk tea"),
    ("Lassi", "Drinks", 150, "Sweet yogurt drink"),
    ("Coke", "Drinks", 80, "330 ml soft drink"),
    ("Fanta", "Drinks", 80, "330 ml soft drink"),
    ("Mineral Water", "Drinks", 30, "500 ml bottle"),
]

ORDER_STATUSES = ["New", "Confirmed", "Cooking", "Ready", "Out for Delivery", "Delivered", "Cancelled"]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> str:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO menu_items (name, category, price, description) VALUES (?,?,?,?)",
                SEED_MENU,
            )
    return str(DB_PATH)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
def get_menu() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM menu_items WHERE available=1 ORDER BY category, name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_menu_items() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM menu_items ORDER BY category, name").fetchall()
    return [dict(r) for r in rows]


def save_menu(rows: list[dict]) -> None:
    """Reconcile an edited menu (list of dicts) with the database.

    Rows with a numeric `id` are updated, rows without one are inserted,
    and rows that disappeared are deleted.
    """
    with get_conn() as conn:
        kept_ids = []
        for r in rows:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            price = float(r.get("price") or 0)
            category = (r.get("category") or "Main").strip() or "Main"
            description = (r.get("description") or "").strip()
            available = 1 if r.get("available", 1) else 0
            rid = _int_id(r.get("id"))
            if rid is not None:
                kept_ids.append(rid)
                conn.execute(
                    "UPDATE menu_items SET name=?, category=?, price=?, description=?, available=? WHERE id=?",
                    (name, category, price, description, available, rid),
                )
            else:
                cur = conn.execute(
                    "INSERT INTO menu_items (name, category, price, description, available) VALUES (?,?,?,?,?)",
                    (name, category, price, description, available),
                )
                kept_ids.append(cur.lastrowid)

        if kept_ids:
            placeholders = ",".join("?" * len(kept_ids))
            conn.execute(
                f"DELETE FROM menu_items WHERE id NOT IN ({placeholders})", kept_ids
            )


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
def create_order(phone, customer_name, address, items, notes="") -> int:
    """items: list of (menu_item_id, item_name, qty, unit_price, customizations)."""
    total = round(sum(qty * price for _, _, qty, price, _ in items), 2)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders (phone, customer_name, address, total, status, notes, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (phone, customer_name, address, total, "New", notes,
             datetime.now().isoformat(timespec="seconds")),
        )
        order_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO order_items (order_id, menu_item_id, item_name, qty, unit_price, customizations) "
            "VALUES (?,?,?,?,?,?)",
            [(order_id, mi, name, qty, price, cust) for mi, name, qty, price, cust in items],
        )
    return order_id


def update_order_status(order_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))


def get_orders() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
        orders = []
        for r in rows:
            d = dict(r)
            d["items"] = [
                dict(x)
                for x in conn.execute(
                    "SELECT * FROM order_items WHERE order_id=? ORDER BY id", (d["id"],)
                ).fetchall()
            ]
            orders.append(d)
    return orders


def get_order_stats() -> dict:
    with get_conn() as conn:
        today = datetime.now().strftime("%Y-%m-%d")
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        today_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (today + "%",)
        ).fetchone()[0]
        revenue = conn.execute("SELECT COALESCE(SUM(total),0) FROM orders").fetchone()[0]
        new = conn.execute("SELECT COUNT(*) FROM orders WHERE status='New'").fetchone()[0]
    return {"total": total_orders, "today": today_orders, "revenue": revenue, "new": new}


# ---------------------------------------------------------------------------
# Call logs
# ---------------------------------------------------------------------------
def log_call(phone, summary, duration_s=0.0) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO call_logs (phone, direction, summary, started_at, duration_s) VALUES (?,?,?,?,?)",
            (phone, "inbound", summary, datetime.now().isoformat(timespec="seconds"), duration_s),
        )
        return cur.lastrowid


def get_call_logs() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM call_logs ORDER BY started_at DESC").fetchall()
    return [dict(r) for r in rows]
