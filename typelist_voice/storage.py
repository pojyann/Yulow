from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .settings import APP_DIR


DB_FILE = APP_DIR / "typelist.db"


class Storage:
    def __init__(self, path: Path = DB_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                text TEXT NOT NULL,
                language TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phrases (
                id INTEGER PRIMARY KEY,
                text TEXT NOT NULL UNIQUE,
                uses INTEGER NOT NULL DEFAULT 1,
                favorite INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def add_history(self, text: str, language: str | None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.connection.execute(
            "INSERT INTO history(text, language, created_at) VALUES(?, ?, ?)",
            (text, language, now),
        )
        self.connection.execute(
            """
            INSERT INTO phrases(text, uses, updated_at) VALUES(?, 1, ?)
            ON CONFLICT(text) DO UPDATE SET uses = uses + 1, updated_at = excluded.updated_at
            """,
            (text, now),
        )
        self.connection.commit()

    def recent_history(self, limit: int = 30) -> list[dict]:
        rows = self.connection.execute(
            "SELECT id, text, language, created_at FROM history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def usage_stats(self) -> dict[str, int]:
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        rows = self.connection.execute(
            "SELECT text, created_at FROM history WHERE created_at >= ?",
            (week_start.isoformat(),),
        ).fetchall()
        return {
            "today": sum(len(row["text"]) for row in rows if row["created_at"][:10] == today.isoformat()),
            "week": sum(len(row["text"]) for row in rows),
            "sessions": len(rows),
        }

    def common_phrases(self, limit: int = 30) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT id, text, uses, favorite FROM phrases
            WHERE favorite = 1 OR uses >= 2
            ORDER BY favorite DESC, uses DESC, updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def favorite(self, text: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.connection.execute(
            """
            INSERT INTO phrases(text, uses, favorite, updated_at) VALUES(?, 1, 1, ?)
            ON CONFLICT(text) DO UPDATE SET favorite = 1, updated_at = excluded.updated_at
            """,
            (text, now),
        )
        self.connection.commit()

    def add_phrase(self, text: str) -> None:
        """Add a user-managed dictionary phrase and keep it visible even before reuse."""
        now = datetime.now().isoformat(timespec="seconds")
        self.connection.execute(
            """
            INSERT INTO phrases(text, uses, favorite, updated_at) VALUES(?, 1, 1, ?)
            ON CONFLICT(text) DO UPDATE SET favorite = 1, updated_at = excluded.updated_at
            """,
            (text, now),
        )
        self.connection.commit()

    def update_phrase(self, item_id: int, text: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.connection.execute(
            "UPDATE phrases SET text = ?, favorite = 1, updated_at = ? WHERE id = ?",
            (text, now, item_id),
        )
        self.connection.commit()

    def delete_phrase(self, item_id: int) -> None:
        self.connection.execute("DELETE FROM phrases WHERE id = ?", (item_id,))
        self.connection.commit()

    def delete_history(self, item_id: int) -> None:
        self.connection.execute("DELETE FROM history WHERE id = ?", (item_id,))
        self.connection.commit()

    def purge_old(self, days: int) -> None:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        self.connection.execute("DELETE FROM history WHERE created_at < ?", (cutoff,))
        self.connection.commit()
