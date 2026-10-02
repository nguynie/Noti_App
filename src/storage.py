import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.json_path = db_path.parent / "seen_posts.json"
        self.init_db()
        self._sync_from_json()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    post_id TEXT NOT NULL,
                    post_url TEXT,
                    creation_time INTEGER,
                    message_snippet TEXT,
                    first_seen_at TEXT NOT NULL,
                    notified INTEGER DEFAULT 0,
                    UNIQUE(source_id, post_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_seen_posts_source_post
                ON seen_posts (source_id, post_id)
                """
            )
            conn.commit()

    def _sync_from_json(self) -> None:
        """Load seen posts from seen_posts.json if available (for git/CI portability)."""
        if not self.json_path.is_file():
            return
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            with self._get_connection() as conn:
                for key, item in data.items():
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO seen_posts
                        (source_id, post_id, post_url, creation_time, message_snippet, first_seen_at, notified)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.get("source_id"),
                            str(item.get("post_id")),
                            item.get("post_url"),
                            item.get("creation_time"),
                            item.get("message_snippet"),
                            item.get("first_seen_at") or datetime.now(timezone.utc).isoformat(),
                            1 if item.get("notified") else 0,
                        ),
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not load state from {self.json_path}: {e}")

    def _sync_to_json(self) -> None:
        """Export all seen posts to seen_posts.json."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT source_id, post_id, post_url, creation_time, message_snippet, first_seen_at, notified
                    FROM seen_posts ORDER BY id ASC
                    """
                )
                rows = cursor.fetchall()

            export_data = {}
            for r in rows:
                key = f"{r['source_id']}:{r['post_id']}"
                export_data[key] = {
                    "source_id": r["source_id"],
                    "post_id": r["post_id"],
                    "post_url": r["post_url"],
                    "creation_time": r["creation_time"],
                    "message_snippet": r["message_snippet"],
                    "first_seen_at": r["first_seen_at"],
                    "notified": bool(r["notified"]),
                }

            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not export state to {self.json_path}: {e}")

    def is_seen(self, source_id: int, post_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM seen_posts WHERE source_id = ? AND post_id = ? LIMIT 1",
                (source_id, post_id),
            )
            return cursor.fetchone() is not None

    def has_source_history(self, source_id: int) -> bool:
        """Check if any posts have ever been recorded for this source."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM seen_posts WHERE source_id = ? LIMIT 1",
                (source_id,),
            )
            return cursor.fetchone() is not None

    def mark_seen(
        self,
        source_id: int,
        post_id: str,
        post_url: Optional[str] = None,
        creation_time: Optional[int] = None,
        message_snippet: Optional[str] = None,
        notified: bool = True,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO seen_posts 
                (source_id, post_id, post_url, creation_time, message_snippet, first_seen_at, notified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    post_id,
                    post_url,
                    creation_time,
                    message_snippet[:200] if message_snippet else None,
                    now_iso,
                    1 if notified else 0,
                ),
            )
            conn.commit()

        # Update JSON file
        self._sync_to_json()

    def get_stats(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_posts")
            total_posts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT source_id) FROM seen_posts")
            tracked_sources = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM seen_posts WHERE notified = 1")
            total_notified = cursor.fetchone()[0]

            return {
                "total_posts": total_posts,
                "tracked_sources": tracked_sources,
                "total_notified": total_notified,
            }
