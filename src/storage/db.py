"""Persistance SQLite : watchlist, portefeuille, anti-spam des alertes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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

    def backup(self, dest_dir: Path | str | None = None, keep: int = 7) -> Path:
        """Sauvegarde à chaud de la base (API backup SQLite) + rotation des anciennes copies."""
        dest_dir = Path(dest_dir) if dest_dir else self.path.parent / "backups"
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        dest = dest_dir / f"owltrader-{stamp}.db"
        with sqlite3.connect(self.path) as src, sqlite3.connect(dest) as dst:
            src.backup(dst)
        backups = sorted(dest_dir.glob("owltrader-*.db"))
        for old in backups[:-keep]:
            old.unlink(missing_ok=True)
        return dest

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
                CREATE TABLE IF NOT EXISTS settings (
                    chat_id INTEGER PRIMARY KEY,
                    sensibilite TEXT DEFAULT 'normale',
                    digest INTEGER DEFAULT 1,
                    langue TEXT DEFAULT 'fr'
                );
                CREATE TABLE IF NOT EXISTS paper_account (
                    chat_id INTEGER PRIMARY KEY,
                    cash REAL, capital REAL, devise TEXT DEFAULT 'EUR',
                    params TEXT, active INTEGER DEFAULT 1, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER, asset TEXT, quantity REAL,
                    entry_price REAL, entry_fee REAL, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER, asset TEXT, side TEXT, quantity REAL,
                    price REAL, fee REAL, pnl REAL, ts TEXT
                );
                CREATE TABLE IF NOT EXISTS paper_equity (
                    chat_id INTEGER, day TEXT, equity REAL,
                    PRIMARY KEY (chat_id, day)
                );
                CREATE TABLE IF NOT EXISTS scan_universe (
                    asset TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS authorized (
                    chat_id INTEGER PRIMARY KEY, ts TEXT
                );
                CREATE TABLE IF NOT EXISTS kv_config (
                    key TEXT PRIMARY KEY, value TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT, chat_id INTEGER, event TEXT, detail TEXT
                );
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER, asset TEXT, target REAL,
                    direction TEXT, created_at TEXT
                );
                """
            )
            # Migration : ajoute la colonne langue aux bases existantes
            cols = [r[1] for r in c.execute("PRAGMA table_info(settings)").fetchall()]
            if "langue" not in cols:
                c.execute("ALTER TABLE settings ADD COLUMN langue TEXT DEFAULT 'fr'")

    # --- Univers de scan/trading (modifiable, sinon défaut config) ---
    def get_universe(self) -> list[str]:
        with self._conn() as c:
            rows = c.execute("SELECT asset FROM scan_universe ORDER BY asset").fetchall()
        return [r["asset"] for r in rows]

    def seed_universe(self, defaults: list[str]):
        with self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM scan_universe").fetchone()[0]
            if n == 0:
                c.executemany("INSERT OR IGNORE INTO scan_universe VALUES (?)",
                              [(a,) for a in defaults])

    def add_to_universe(self, asset: str):
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO scan_universe VALUES (?)", (asset,))

    def remove_from_universe(self, asset: str):
        with self._conn() as c:
            c.execute("DELETE FROM scan_universe WHERE asset=?", (asset,))

    # --- Alertes de prix ---
    def add_price_alert(self, chat_id: int, asset: str, target: float, direction: str):
        with self._conn() as c:
            c.execute(
                "INSERT INTO price_alerts (chat_id, asset, target, direction, created_at) VALUES (?,?,?,?,?)",
                (chat_id, asset, target, direction, datetime.now(timezone.utc).isoformat()),
            )

    def get_price_alerts(self, chat_id: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM price_alerts WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()
        return [dict(r) for r in rows]

    def all_price_alerts(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM price_alerts").fetchall()
        return [dict(r) for r in rows]

    def remove_price_alert(self, alert_id: int, chat_id: int | None = None):
        with self._conn() as c:
            if chat_id is None:
                c.execute("DELETE FROM price_alerts WHERE id=?", (alert_id,))
            else:
                c.execute("DELETE FROM price_alerts WHERE id=? AND chat_id=?", (alert_id, chat_id))

    # --- Compte de paper-trading autonome ---
    def paper_open(self, chat_id: int, capital: float, devise: str = "EUR", params: str | None = None):
        """Crée OU réinitialise le compte (remet les mises et efface les actions)."""
        with self._conn() as c:
            c.execute("DELETE FROM paper_positions WHERE chat_id=?", (chat_id,))
            c.execute("DELETE FROM paper_trades WHERE chat_id=?", (chat_id,))
            c.execute("DELETE FROM paper_equity WHERE chat_id=?", (chat_id,))
            c.execute(
                "INSERT OR REPLACE INTO paper_account (chat_id, cash, capital, devise, params, active, created_at) "
                "VALUES (?,?,?,?,?,1,?)",
                (chat_id, capital, capital, devise, params,
                 datetime.now(timezone.utc).isoformat()),
            )

    def paper_get(self, chat_id: int) -> Optional[dict]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM paper_account WHERE chat_id=?", (chat_id,)).fetchone()
        return dict(row) if row else None

    def paper_set_cash(self, chat_id: int, cash: float):
        with self._conn() as c:
            c.execute("UPDATE paper_account SET cash=? WHERE chat_id=?", (cash, chat_id))

    def paper_set_params(self, chat_id: int, params: str):
        with self._conn() as c:
            c.execute("UPDATE paper_account SET params=? WHERE chat_id=?", (params, chat_id))

    def paper_set_active(self, chat_id: int, active: int):
        with self._conn() as c:
            c.execute("UPDATE paper_account SET active=? WHERE chat_id=?", (active, chat_id))

    def paper_active_chats(self) -> list[int]:
        with self._conn() as c:
            rows = c.execute("SELECT chat_id FROM paper_account WHERE active=1").fetchall()
        return [r["chat_id"] for r in rows]

    def paper_positions(self, chat_id: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM paper_positions WHERE chat_id=?", (chat_id,)).fetchall()
        return [dict(r) for r in rows]

    def paper_add_position(self, chat_id: int, asset: str, qty: float, price: float, fee: float):
        with self._conn() as c:
            c.execute(
                "INSERT INTO paper_positions (chat_id, asset, quantity, entry_price, entry_fee, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (chat_id, asset, qty, price, fee, datetime.now(timezone.utc).isoformat()),
            )

    def paper_remove_position(self, chat_id: int, asset: str):
        with self._conn() as c:
            c.execute("DELETE FROM paper_positions WHERE chat_id=? AND asset=?", (chat_id, asset))

    def paper_record_trade(self, chat_id: int, asset: str, side: str, qty: float,
                           price: float, fee: float, pnl: float = 0.0):
        with self._conn() as c:
            c.execute(
                "INSERT INTO paper_trades (chat_id, asset, side, quantity, price, fee, pnl, ts) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (chat_id, asset, side, qty, price, fee, pnl, datetime.now(timezone.utc).isoformat()),
            )

    def paper_trades_since(self, chat_id: int, since_iso: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM paper_trades WHERE chat_id=? AND ts>=? ORDER BY ts", (chat_id, since_iso)
            ).fetchall()
        return [dict(r) for r in rows]

    def paper_record_equity(self, chat_id: int, equity: float):
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO paper_equity VALUES (?,?,?)", (chat_id, day, equity))

    def paper_equity_curve(self, chat_id: int) -> list[tuple[str, float]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT day, equity FROM paper_equity WHERE chat_id=? ORDER BY day", (chat_id,)
            ).fetchall()
        return [(r["day"], r["equity"]) for r in rows]

    # --- Réglages par utilisateur ---
    def get_settings(self, chat_id: int) -> dict:
        with self._conn() as c:
            row = c.execute("SELECT * FROM settings WHERE chat_id=?", (chat_id,)).fetchone()
        if row:
            return dict(row)
        return {"chat_id": chat_id, "sensibilite": "normale", "digest": 1, "langue": "fr"}

    # --- Config clé-valeur CHIFFRÉE (modifiable depuis Telegram : clés API, etc.) ---
    def get_config(self, key: str) -> Optional[str]:
        from ..crypto import decrypt
        with self._conn() as c:
            row = c.execute("SELECT value FROM kv_config WHERE key=?", (key,)).fetchone()
        return decrypt(row["value"]) if row else None

    def set_config(self, key: str, value: str):
        from ..crypto import encrypt
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO kv_config VALUES (?,?)", (key, encrypt(value)))

    def del_config(self, key: str):
        with self._conn() as c:
            c.execute("DELETE FROM kv_config WHERE key=?", (key,))

    def all_config(self) -> dict:
        from ..crypto import decrypt
        with self._conn() as c:
            return {r["key"]: decrypt(r["value"])
                    for r in c.execute("SELECT key, value FROM kv_config").fetchall()}

    # --- Contrôle d'accès (mot de passe) ---
    def is_authorized(self, chat_id: int) -> bool:
        with self._conn() as c:
            return c.execute("SELECT 1 FROM authorized WHERE chat_id=?", (chat_id,)).fetchone() is not None

    def authorize(self, chat_id: int):
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO authorized VALUES (?,?)",
                      (chat_id, datetime.now(timezone.utc).isoformat()))

    def deauthorize(self, chat_id: int):
        with self._conn() as c:
            c.execute("DELETE FROM authorized WHERE chat_id=?", (chat_id,))

    def all_authorized(self) -> list[int]:
        with self._conn() as c:
            return [r["chat_id"] for r in c.execute("SELECT chat_id FROM authorized").fetchall()]

    # --- Journal d'audit de sécurité ---
    def log_event(self, chat_id: int, event: str, detail: str = ""):
        with self._conn() as c:
            c.execute("INSERT INTO audit_log (ts, chat_id, event, detail) VALUES (?,?,?,?)",
                      (datetime.now(timezone.utc).isoformat(), chat_id, event, detail))
            # rotation : on garde les 500 derniers évènements
            c.execute("DELETE FROM audit_log WHERE id NOT IN "
                      "(SELECT id FROM audit_log ORDER BY id DESC LIMIT 500)")

    def recent_audit(self, limit: int = 12) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def has_settings(self, chat_id: int) -> bool:
        with self._conn() as c:
            return c.execute("SELECT 1 FROM settings WHERE chat_id=?", (chat_id,)).fetchone() is not None

    def set_setting(self, chat_id: int, key: str, value):
        if key not in ("sensibilite", "digest", "langue"):
            raise ValueError(key)
        with self._conn() as c:
            c.execute(
                "INSERT INTO settings (chat_id) VALUES (?) ON CONFLICT(chat_id) DO NOTHING",
                (chat_id,),
            )
            c.execute(f"UPDATE settings SET {key}=? WHERE chat_id=?", (value, chat_id))

    def chats_with_digest(self) -> list[int]:
        with self._conn() as c:
            rows = c.execute("SELECT chat_id FROM settings WHERE digest=1").fetchall()
        return [r["chat_id"] for r in rows]

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
