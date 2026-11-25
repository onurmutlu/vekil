"""SQLite persistence. One process, one file; move to PostgreSQL to scale out."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
    owner_id INTEGER PRIMARY KEY,           -- Telegram user id of the business account
    owner_name TEXT NOT NULL DEFAULT '',
    connection_id TEXT UNIQUE,              -- current business_connection id
    user_chat_id INTEGER,                   -- private chat between owner and our bot
    connected INTEGER NOT NULL DEFAULT 0,   -- Telegram says the connection is enabled
    can_reply INTEGER NOT NULL DEFAULT 0,   -- owner granted the reply right
    active INTEGER NOT NULL DEFAULT 0,      -- owner switched the assistant on in the dashboard
    business_name TEXT NOT NULL DEFAULT '',
    about TEXT NOT NULL DEFAULT '',
    knowledge TEXT NOT NULL DEFAULT '',
    tone TEXT NOT NULL DEFAULT '',
    handoff_note TEXT NOT NULL DEFAULT '',
    pause_minutes INTEGER NOT NULL DEFAULT 30,
    trial_used INTEGER NOT NULL DEFAULT 0,
    period_used INTEGER NOT NULL DEFAULT 0,
    quota_notice REAL NOT NULL DEFAULT 0,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chats(
    owner_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    customer_name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ai',       -- ai | handoff
    handoff_reason TEXT NOT NULL DEFAULT '',
    paused_until REAL NOT NULL DEFAULT 0,
    last_text TEXT NOT NULL DEFAULT '',
    last_at REAL NOT NULL DEFAULT 0,
    PRIMARY KEY(owner_id, chat_id)
);
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('customer','assistant','owner')),
    text TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_chat ON messages(owner_id, chat_id, id);
CREATE TABLE IF NOT EXISTS seen(owner_id INTEGER, chat_id INTEGER, message_id INTEGER,
    PRIMARY KEY(owner_id, chat_id, message_id));
CREATE TABLE IF NOT EXISTS replies(owner_id INTEGER, chat_id INTEGER, created REAL);
CREATE INDEX IF NOT EXISTS replies_chat ON replies(owner_id, chat_id, created);
CREATE TABLE IF NOT EXISTS playground(owner_id INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, owner_id INTEGER, stars INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS payments(
    charge TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, stars INTEGER NOT NULL,
    expires REAL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS refunds(charge TEXT PRIMARY KEY, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS payment_issues(
    charge TEXT PRIMARY KEY, owner_id INTEGER, stars INTEGER, payload TEXT, reason TEXT, created REAL);
"""

PROFILE_FIELDS = {
    "business_name": 64,
    "about": 1000,
    "knowledge": 8000,
    "tone": 300,
    "handoff_note": 500,
}


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        if str(path) != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    # accounts -----------------------------------------------------------------
    def account(self, owner_id: int):
        return self.db.execute("SELECT * FROM accounts WHERE owner_id=?", (owner_id,)).fetchone()

    def account_by_connection(self, connection_id: str):
        return self.db.execute("SELECT * FROM accounts WHERE connection_id=?", (connection_id,)).fetchone()

    def ensure_account(self, owner_id: int, owner_name: str = ""):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO accounts(owner_id, owner_name, created) VALUES(?,?,?)",
                            (owner_id, owner_name[:64], time.time()))
        return self.account(owner_id)

    def set_connection(self, owner_id: int, owner_name: str, connection_id: str, user_chat_id: int,
                       connected: bool, can_reply: bool) -> None:
        self.ensure_account(owner_id, owner_name)
        with self.db:
            # A connection id belongs to exactly one account.
            self.db.execute("UPDATE accounts SET connection_id=NULL WHERE connection_id=? AND owner_id<>?",
                            (connection_id, owner_id))
            self.db.execute(
                "UPDATE accounts SET connection_id=?, user_chat_id=?, connected=?, can_reply=?, owner_name=? "
                "WHERE owner_id=?",
                (connection_id, user_chat_id, int(connected), int(can_reply), owner_name[:64], owner_id))

    def update_profile(self, owner_id: int, values: dict) -> None:
        sets, params = [], []
        for key, limit in PROFILE_FIELDS.items():
            if key in values:
                sets.append(f"{key}=?")
                params.append(str(values[key])[:limit])
        if "pause_minutes" in values:
            sets.append("pause_minutes=?")
            params.append(max(1, min(1440, int(values["pause_minutes"]))))
        if not sets:
            return
        with self.db:
            self.db.execute(f"UPDATE accounts SET {', '.join(sets)} WHERE owner_id=?", (*params, owner_id))

    def set_active(self, owner_id: int, active: bool) -> None:
        with self.db:
            self.db.execute("UPDATE accounts SET active=? WHERE owner_id=?", (int(active), owner_id))

    # chats and messages -----------------------------------------------------------
    def chat(self, owner_id: int, chat_id: int):
        return self.db.execute("SELECT * FROM chats WHERE owner_id=? AND chat_id=?", (owner_id, chat_id)).fetchone()

    def touch_chat(self, owner_id: int, chat_id: int, name: str, username: str, text: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO chats(owner_id,chat_id,customer_name,username,last_text,last_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(owner_id,chat_id) DO UPDATE SET customer_name=excluded.customer_name, "
                "username=excluded.username, last_text=excluded.last_text, last_at=excluded.last_at",
                (owner_id, chat_id, name[:64], username[:64], text[:200], time.time()))

    def set_chat_status(self, owner_id: int, chat_id: int, status: str, reason: str = "") -> None:
        with self.db:
            self.db.execute("UPDATE chats SET status=?, handoff_reason=? WHERE owner_id=? AND chat_id=?",
                            (status, reason[:300], owner_id, chat_id))

    def pause_chat(self, owner_id: int, chat_id: int, until: float) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO chats(owner_id,chat_id,paused_until) VALUES(?,?,?) "
                "ON CONFLICT(owner_id,chat_id) DO UPDATE SET paused_until=excluded.paused_until",
                (owner_id, chat_id, until))

    def chats(self, owner_id: int, limit: int = 100):
        return self.db.execute("SELECT * FROM chats WHERE owner_id=? ORDER BY last_at DESC LIMIT ?",
                               (owner_id, limit)).fetchall()

    def add_message(self, owner_id: int, chat_id: int, role: str, text: str) -> None:
        with self.db:
            self.db.execute("INSERT INTO messages(owner_id,chat_id,role,text,created) VALUES(?,?,?,?,?)",
                            (owner_id, chat_id, role, text[:4000], time.time()))

    def history(self, owner_id: int, chat_id: int, limit: int):
        rows = self.db.execute(
            "SELECT role,text FROM messages WHERE owner_id=? AND chat_id=? ORDER BY id DESC LIMIT ?",
            (owner_id, chat_id, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def first_time(self, owner_id: int, chat_id: int, message_id: int) -> bool:
        """True once per message: webhook retries must not produce a second answer."""
        with self.db:
            cur = self.db.execute("INSERT OR IGNORE INTO seen VALUES(?,?,?)", (owner_id, chat_id, message_id))
        return cur.rowcount == 1

    def forget(self, owner_id: int, chat_id: int, message_id: int) -> None:
        with self.db:
            self.db.execute("DELETE FROM seen WHERE owner_id=? AND chat_id=? AND message_id=?",
                            (owner_id, chat_id, message_id))
            # the customer message will be stored again on retry
            self.db.execute(
                "DELETE FROM messages WHERE id=(SELECT MAX(id) FROM messages WHERE owner_id=? AND chat_id=? "
                "AND role='customer')", (owner_id, chat_id))

    def replies_last_hour(self, owner_id: int, chat_id: int) -> int:
        return self.db.execute("SELECT COUNT(*) FROM replies WHERE owner_id=? AND chat_id=? AND created>?",
                               (owner_id, chat_id, time.time() - 3600)).fetchone()[0]

    def count_reply(self, owner_id: int, chat_id: int, paid: bool) -> None:
        with self.db:
            self.db.execute("INSERT INTO replies VALUES(?,?,?)", (owner_id, chat_id, time.time()))
            column = "period_used" if paid else "trial_used"
            self.db.execute(f"UPDATE accounts SET {column}={column}+1 WHERE owner_id=?", (owner_id,))

    def playground_today(self, owner_id: int) -> int:
        return self.db.execute("SELECT COUNT(*) FROM playground WHERE owner_id=? AND created>?",
                               (owner_id, time.time() - 86400)).fetchone()[0]

    def count_playground(self, owner_id: int) -> None:
        with self.db:
            self.db.execute("INSERT INTO playground VALUES(?,?)", (owner_id, time.time()))

    def set_quota_notice(self, owner_id: int, when: float) -> None:
        with self.db:
            self.db.execute("UPDATE accounts SET quota_notice=? WHERE owner_id=?", (when, owner_id))

    # billing --------------------------------------------------------------------
    def plan_until(self, owner_id: int) -> float:
        row = self.db.execute(
            "SELECT MAX(p.expires) FROM payments p WHERE p.owner_id=? "
            "AND NOT EXISTS (SELECT 1 FROM refunds r WHERE r.charge=p.charge)", (owner_id,)).fetchone()
        return row[0] or 0

    def create_order(self, order_id: str, owner_id: int, stars: int) -> None:
        with self.db:
            self.db.execute("INSERT INTO orders VALUES(?,?,?,?)", (order_id, owner_id, stars, time.time()))

    def order(self, order_id: str):
        return self.db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    def payment(self, charge: str):
        return self.db.execute("SELECT * FROM payments WHERE charge=?", (charge,)).fetchone()

    def add_payment(self, charge: str, owner_id: int, stars: int, expires: float) -> None:
        """Each paid period starts with a fresh reply allowance."""
        with self.db:
            self.db.execute("INSERT INTO payments VALUES(?,?,?,?,?)", (charge, owner_id, stars, expires, time.time()))
            self.db.execute("UPDATE accounts SET period_used=0, quota_notice=0 WHERE owner_id=?", (owner_id,))

    def mark_refunded(self, charge: str) -> None:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO refunds VALUES(?,?)", (charge, time.time()))

    def is_refunded(self, charge: str) -> bool:
        return self.db.execute("SELECT 1 FROM refunds WHERE charge=?", (charge,)).fetchone() is not None

    def record_issue(self, charge, owner_id, stars, payload, reason) -> None:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO payment_issues VALUES(?,?,?,?,?,?)",
                            (charge, owner_id, stars, payload, reason, time.time()))

    def open_issues(self):
        return self.db.execute(
            "SELECT i.* FROM payment_issues i WHERE NOT EXISTS (SELECT 1 FROM refunds r WHERE r.charge=i.charge) "
            "ORDER BY created").fetchall()
