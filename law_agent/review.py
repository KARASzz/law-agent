"""
人工审阅任务存储。

保存中高风险输出的审阅状态、确认前内容、确认后内容和审阅人信息。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ReviewTask:
    trace_id: str
    task_id: str
    session_id: str
    user_id: str
    intent: str
    risk_level: str
    review_status: str
    original_output: str
    user_input: Optional[str] = None
    task_title: Optional[str] = None
    reviewed_output: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "intent": self.intent,
            "risk_level": self.risk_level,
            "review_status": self.review_status,
            "original_output": self.original_output,
            "user_input": self.user_input,
            "task_title": self.task_title,
            "reviewed_output": self.reviewed_output,
            "reviewer_id": self.reviewer_id,
            "reviewed_at": self.reviewed_at,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ReviewTaskStore:
    """SQLite 版人工审阅任务库。"""

    def __init__(self, db_path: str = "data/tasks.db"):
        self.db_path = db_path
        self._memory_conn = None
        self._init_database()

    def _connect(self):
        if self.db_path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(self.db_path)
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn):
        if self.db_path != ":memory:":
            conn.close()

    def _init_database(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS review_tasks (
                trace_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                session_id TEXT,
                user_id TEXT,
                intent TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                review_status TEXT NOT NULL,
                original_output TEXT NOT NULL,
                user_input TEXT,
                task_title TEXT,
                reviewed_output TEXT,
                reviewer_id TEXT,
                reviewed_at TEXT,
                rejection_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._ensure_column(cursor, "review_tasks", "user_input", "TEXT")
        self._ensure_column(cursor, "review_tasks", "task_title", "TEXT")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_status ON review_tasks(review_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_user_id ON review_tasks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_risk_level ON review_tasks(risk_level)")
        conn.commit()
        self._close(conn)

    def create_pending(
        self,
        trace_id: str,
        task_id: str,
        session_id: str,
        user_id: str,
        intent: str,
        risk_level: str,
        original_output: str,
        user_input: str = "",
        task_title: str = "",
    ) -> ReviewTask:
        now = datetime.now().isoformat(timespec="seconds")
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO review_tasks (
                    trace_id, task_id, session_id, user_id, intent, risk_level,
                    review_status, original_output, user_input, task_title,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    intent = excluded.intent,
                    risk_level = excluded.risk_level,
                    review_status = excluded.review_status,
                    original_output = excluded.original_output,
                    user_input = excluded.user_input,
                    task_title = excluded.task_title,
                    updated_at = excluded.updated_at
                """,
                (
                    trace_id,
                    task_id,
                    session_id,
                    user_id,
                    intent,
                    risk_level,
                    "pending_review",
                    original_output,
                    user_input,
                    task_title,
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            self._close(conn)
        return self.get(trace_id)

    def update_task_metadata(
        self,
        trace_id: str,
        user_input: Optional[str] = None,
        task_title: Optional[str] = None,
    ) -> Optional[ReviewTask]:
        """补充审阅任务展示元数据。"""
        updates = []
        params = []
        if user_input is not None:
            updates.append("user_input = ?")
            params.append(user_input)
        if task_title is not None:
            updates.append("task_title = ?")
            params.append(task_title)
        if not updates:
            return self.get(trace_id)

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat(timespec="seconds"))
        params.append(trace_id)

        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE review_tasks SET {', '.join(updates)} WHERE trace_id = ?",
                params,
            )
            conn.commit()
        finally:
            self._close(conn)
        return self.get(trace_id)

    def get(self, trace_id: str) -> Optional[ReviewTask]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM review_tasks WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
        finally:
            self._close(conn)
        return self._row_to_task(row) if row else None

    def list_tasks(
        self,
        review_status: Optional[str] = None,
        user_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 100,
    ) -> list[ReviewTask]:
        """按状态、用户或风险等级查询审阅任务。"""
        conditions = []
        params = []

        if review_status:
            conditions.append("review_status = ?")
            params.append(review_status)

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if risk_level:
            conditions.append("risk_level = ?")
            params.append(risk_level)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM review_tasks
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT ?
        """
        params.append(limit)

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            self._close(conn)

        return [self._row_to_task(row) for row in rows]

    def confirm(
        self,
        trace_id: str,
        reviewer_id: str,
        reviewed_output: Optional[str] = None,
    ) -> Optional[ReviewTask]:
        task = self.get(trace_id)
        if task is None:
            return None

        now = datetime.now().isoformat(timespec="seconds")
        final_output = reviewed_output if reviewed_output is not None else task.original_output
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE review_tasks
                SET review_status = ?, reviewed_output = ?, reviewer_id = ?,
                    reviewed_at = ?, rejection_reason = NULL, updated_at = ?
                WHERE trace_id = ?
                """,
                ("confirmed", final_output, reviewer_id, now, now, trace_id),
            )
            conn.commit()
        finally:
            self._close(conn)
        return self.get(trace_id)

    def reject(
        self,
        trace_id: str,
        reviewer_id: str,
        rejection_reason: str,
    ) -> Optional[ReviewTask]:
        task = self.get(trace_id)
        if task is None:
            return None

        now = datetime.now().isoformat(timespec="seconds")
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE review_tasks
                SET review_status = ?, reviewer_id = ?, reviewed_at = ?,
                    rejection_reason = ?, updated_at = ?
                WHERE trace_id = ?
                """,
                ("rejected", reviewer_id, now, rejection_reason, now, trace_id),
            )
            conn.commit()
        finally:
            self._close(conn)
        return self.get(trace_id)

    def _row_to_task(self, row: sqlite3.Row) -> ReviewTask:
        return ReviewTask(**dict(row))

    def _ensure_column(
        self,
        cursor: sqlite3.Cursor,
        table_name: str,
        column_name: str,
        column_type: str,
    ):
        existing = {
            row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in existing:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )
