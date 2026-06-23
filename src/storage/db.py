"""Persistance SQLite : watchlist, portefeuille, anti-spam des alertes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "owltrader.db"


class Storage:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS watchlist (
                    chat_id INTEGER, asset TEXT, PRIMARY KEY (chat_id, asset)
                );
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER, asset TEXT, quantity REAL,
                    buy_price REAL, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS last_alert (
                    chat_id INTEGER, asset TEXT, direction TEXT, sent_at TEXT,
                    PRIMARY KEY (chat_id, asset)
                );
                """
            )

    # --- Watchlist ---
    def add_watch(self, chat_id: int, asset: str):
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO watchlist VALUES (?,?)", (chat_id, asset))

    def remove_watch(self, chat_id: int, asset: str):
        with self._conn() as c:
            c.execute("DELETE FROM watchlist WHERE chat_id=? AND asset=?", (chat_id, asset))

    def get_watch(self, chat_id: int) -> list[str]:
        with self._conn() as c:
            rows = c.execute("SELECT asset FROM watchlist WHERE chat_id=?", (chat_id,)).fetchall()
        return [r["asset"] for r in rows]

    def all_watched_pairs(self) -> list[tuple[int, str]]:
        with self._conn() as c:
            rows = c.execute("SELECT chat_id, asset FROM watchlist").fetchall()
        return [(r["chat_id"], r["asset"]) for r in rows]

    # --- Portefeuille ---
    def add_position(self, chat_id: int, asset: str, qty: float, price: float):
        with self._conn() as c:
            c.execute(
                "INSERT INTO portfolio (chat_id, asset, quantity, buy_price, created_at) VALUES (?,?,?,?,?)",
                (chat_id, asset, qty, price, datetime.now(timezone.utc).isoformat()),
            )

    def get_positions(self, chat_id: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM portfolio WHERE chat_id=?", (chat_id,)).fetchall()
        return [dict(r) for r in rows]

    def remove_position(self, chat_id: int, pos_id: int):
        with self._conn() as c:
            c.execute("DELETE FROM portfolio WHERE id=? AND chat_id=?", (pos_id, chat_id))

    # --- Anti-spam des alertes ---
    def should_alert(self, chat_id: int, asset: str, direction: str, min_hours: float) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT direction, sent_at FROM last_alert WHERE chat_id=? AND asset=?",
                (chat_id, asset),
            ).fetchone()
            if row and row["direction"] == direction:
                last = datetime.fromisoformat(row["sent_at"])
                if (datetime.now(timezone.utc) - last).total_seconds() < min_hours * 3600:
                    return False
            c.execute(
                "INSERT OR REPLACE INTO last_alert VALUES (?,?,?,?)",
                (chat_id, asset, direction, datetime.now(timezone.utc).isoformat()),
            )
        return True
