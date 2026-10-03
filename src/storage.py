from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
import os
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

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

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
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_seen_posts_source_url
                ON seen_posts (source_id, post_url)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
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
                    if key == "_metadata" and isinstance(item, dict):
                        for m_k, m_v in item.items():
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO app_metadata (key, value)
                                VALUES (?, ?)
                                """,
                                (m_k, str(m_v)),
                            )
                        continue
                    if key.startswith("_") or not isinstance(item, dict):
                        continue
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
                            item.get("first_seen_at")
                            or datetime.now(timezone.utc).isoformat(),
                            1 if item.get("notified") else 0,
                        ),
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not load state from {self.json_path}: {e}")

    def _sync_to_json(self) -> None:
        """Export all seen posts atomically to seen_posts.json."""
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

                cursor.execute("SELECT key, value FROM app_metadata")
                meta_rows = cursor.fetchall()

            export_data = {}
            if meta_rows:
                export_data["_metadata"] = {r["key"]: r["value"] for r in meta_rows}

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

            tmp_file = self.json_path.with_suffix(".json.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, self.json_path)
        except Exception as e:
            logger.warning(f"Could not export state to {self.json_path}: {e}")

    def sync_to_json(self) -> None:
        """Public alias to force export to JSON."""
        self._sync_to_json()

    def get_metadata(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM app_metadata WHERE key = ? LIMIT 1",
                (key,),
            )
            row = cursor.fetchone()
            if row is not None:
                return row["value"]
            return default

    def set_metadata(self, key: str, value: str, sync_json: bool = True) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO app_metadata (key, value)
                VALUES (?, ?)
                """,
                (key, str(value)),
            )
            conn.commit()
        if sync_json:
            self._sync_to_json()

    def is_seen(
        self,
        source_id: int,
        post_id: str,
        post_url: Optional[str] = None,
    ) -> bool:
        pid_str = str(post_id).strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Exact match on (source_id, post_id)
            cursor.execute(
                "SELECT 1 FROM seen_posts WHERE source_id = ? AND post_id = ? LIMIT 1",
                (source_id, pid_str),
            )
            if cursor.fetchone() is not None:
                return True

            # 2. Match exact post_url if provided
            if post_url:
                cursor.execute(
                    "SELECT 1 FROM seen_posts WHERE source_id = ? AND post_url = ? LIMIT 1",
                    (source_id, post_url),
                )
                if cursor.fetchone() is not None:
                    return True

            # 3. Check if post_id appears inside any stored post_url
            if len(pid_str) >= 6:
                cursor.execute(
                    "SELECT 1 FROM seen_posts WHERE source_id = ? AND post_url LIKE ? LIMIT 1",
                    (source_id, f"%{pid_str}%"),
                )
                if cursor.fetchone() is not None:
                    return True

            # 4. Check if any stored post_id appears in the query post_url
            if post_url:
                cursor.execute(
                    "SELECT post_id FROM seen_posts WHERE source_id = ?",
                    (source_id,),
                )
                for row in cursor.fetchall():
                    stored_pid = str(row["post_id"])
                    if len(stored_pid) >= 6 and stored_pid in post_url:
                        return True

            return False

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
        sync_json: bool = True,
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
                    str(post_id),
                    post_url,
                    creation_time,
                    message_snippet[:200] if message_snippet else None,
                    now_iso,
                    1 if notified else 0,
                ),
            )
            conn.commit()

        if sync_json:
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
