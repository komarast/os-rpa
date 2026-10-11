import sqlite3
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from os_rpa.models import QueueItem, QueueItemStatus, utc_now_iso


class QueueManager:
    """Manages transactional RPA work queues backed by SQLite."""

    def __init__(self, db_path: str = "data/rpa_queues.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queue_items (
                    id TEXT PRIMARY KEY,
                    queue_name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    error_message TEXT,
                    output_data TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_queue_status_prio 
                ON queue_items(queue_name, status, priority DESC, created_at ASC)
            """)
            conn.commit()

    def add_item(
        self,
        queue_name: str,
        payload: Dict[str, Any],
        priority: int = 0,
        max_retries: int = 3,
    ) -> QueueItem:
        item = QueueItem(
            queue_name=queue_name,
            payload=payload,
            status=QueueItemStatus.NEW,
            priority=priority,
            max_retries=max_retries,
        )
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO queue_items (
                    id, queue_name, payload, status, priority, retry_count,
                    max_retries, error_message, output_data, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.queue_name,
                    json.dumps(item.payload),
                    item.status.value,
                    item.priority,
                    item.retry_count,
                    item.max_retries,
                    item.error_message,
                    json.dumps(item.output_data) if item.output_data else None,
                    item.created_at,
                    item.updated_at,
                ),
            )
            conn.commit()
        return item

    def add_items(self, queue_name: str, payloads: List[Dict[str, Any]], priority: int = 0) -> List[QueueItem]:
        items = []
        for p in payloads:
            items.append(self.add_item(queue_name, p, priority=priority))
        return items

    def get_next_item(self, queue_name: str) -> Optional[QueueItem]:
        """Atomically retrieves the next highest priority NEW item and marks it IN_PROGRESS."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM queue_items
                WHERE queue_name = ? AND status = ?
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """,
                (queue_name, QueueItemStatus.NEW.value),
            )
            row = cursor.fetchone()
            if not row:
                return None

            item_id = row["id"]
            now = utc_now_iso()
            cursor.execute(
                """
                UPDATE queue_items
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (QueueItemStatus.IN_PROGRESS.value, now, item_id),
            )
            conn.commit()

            cursor.execute("SELECT * FROM queue_items WHERE id = ?", (item_id,))
            updated_row = cursor.fetchone()
            return self._row_to_model(updated_row) if updated_row else None

    def set_status(
        self,
        item_id: str,
        status: QueueItemStatus,
        error_message: Optional[str] = None,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[QueueItem]:
        now = utc_now_iso()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE queue_items
                SET status = ?, error_message = ?, output_data = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value if isinstance(status, QueueItemStatus) else status,
                    error_message,
                    json.dumps(output_data) if output_data is not None else None,
                    now,
                    item_id,
                ),
            )
            conn.commit()
        return self.get_item(item_id)

    def fail_and_retry(
        self,
        item_id: str,
        error_message: str,
    ) -> QueueItem:
        """Fails the item. If retry_count < max_retries, it becomes NEW again with incremented retry_count."""
        item = self.get_item(item_id)
        if not item:
            raise ValueError(f"Queue item {item_id} not found")

        now = utc_now_iso()
        new_retries = item.retry_count + 1
        if new_retries <= item.max_retries:
            next_status = QueueItemStatus.NEW
        else:
            next_status = QueueItemStatus.FAILED

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE queue_items
                SET status = ?, retry_count = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_status.value, new_retries, error_message, now, item_id),
            )
            conn.commit()
        return self.get_item(item_id)

    def get_item(self, item_id: str) -> Optional[QueueItem]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM queue_items WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_model(row)

    def list_items(
        self,
        queue_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[QueueItem]:
        query = "SELECT * FROM queue_items WHERE 1=1"
        params: List[Any] = []
        if queue_name:
            query += " AND queue_name = ?"
            params.append(queue_name)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_model(r) for r in cursor.fetchall()]

    def list_queues(self) -> List[Dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    queue_name,
                    COUNT(*) as total_items,
                    SUM(CASE WHEN status = 'NEW' THEN 1 ELSE 0 END) as new_items,
                    SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress_items,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_items,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_items,
                    SUM(CASE WHEN status = 'ABANDONED' THEN 1 ELSE 0 END) as abandoned_items,
                    MAX(created_at) as last_activity
                FROM queue_items
                GROUP BY queue_name
                ORDER BY queue_name ASC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def delete_item(self, item_id: str) -> bool:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM queue_items WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_queue(self, queue_name: str) -> int:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM queue_items WHERE queue_name = ?", (queue_name,))
            conn.commit()
            return cursor.rowcount

    def _row_to_model(self, row: sqlite3.Row) -> QueueItem:
        return QueueItem(
            id=row["id"],
            queue_name=row["queue_name"],
            payload=json.loads(row["payload"]),
            status=QueueItemStatus(row["status"]),
            priority=row["priority"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            error_message=row["error_message"],
            output_data=json.loads(row["output_data"]) if row["output_data"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

