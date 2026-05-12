"""Hierarchical Orchestrator 任务存储。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional

from .models import (
    SQLMODEL_AVAILABLE,
    OrchestrationStep,
    OrchestrationTask,
    ToolCallRecord,
    now_iso,
)

if SQLMODEL_AVAILABLE:  # pragma: no cover - 依赖安装后由集成环境覆盖
    from sqlmodel import SQLModel, Session, create_engine, select


class OrchestrationStore:
    """任务、步骤和工具调用记录库。优先使用 SQLModel，缺依赖时回退 sqlite3。"""

    def __init__(self, db_path: str = "data/orchestration.db"):
        self.db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        self._engine = None
        if SQLMODEL_AVAILABLE:
            sqlite_url = "sqlite://" if db_path == ":memory:" else f"sqlite:///{db_path}"
            if db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
            SQLModel.metadata.create_all(
                self._engine,
                tables=[
                    OrchestrationTask.__table__,
                    OrchestrationStep.__table__,
                    ToolCallRecord.__table__,
                ],
            )
        else:
            self._init_sqlite()

    def create_task(
        self,
        task_id: str,
        trace_id: str,
        session_id: str,
        user_id: str,
        user_input: str,
    ) -> OrchestrationTask:
        task = OrchestrationTask(
            task_id=task_id,
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
            status="running",
        )
        self._save_task(task)
        return task

    def update_task(
        self,
        task_id: str,
        status: str,
        intent: str = "",
        risk_level: str = "",
        final_output: str = "",
        error: str = "",
    ) -> Optional[OrchestrationTask]:
        task = self.get_task(task_id)
        if not task:
            return None
        task.status = status
        if intent:
            task.intent = intent
        if risk_level:
            task.risk_level = risk_level
        if final_output:
            task.final_output = final_output
        if error:
            task.error = error
        task.updated_at = now_iso()
        self._save_task(task)
        return task

    def add_step(
        self,
        task_id: str,
        name: str,
        role: str,
        sequence: int,
        parent_step_id: str | None = None,
        input_data: Optional[dict[str, Any]] = None,
    ) -> OrchestrationStep:
        step = OrchestrationStep(
            step_id=str(uuid.uuid4()),
            task_id=task_id,
            parent_step_id=parent_step_id,
            sequence=sequence,
            name=name,
            role=role,
            status="running",
            input_json=json.dumps(input_data or {}, ensure_ascii=False),
        )
        self._save_step(step)
        return step

    def finish_step(
        self,
        step_id: str,
        status: str = "completed",
        output_data: Optional[dict[str, Any]] = None,
        error: str = "",
    ) -> Optional[OrchestrationStep]:
        step = self.get_step(step_id)
        if not step:
            return None
        step.status = status
        step.output_json = json.dumps(output_data or {}, ensure_ascii=False)
        step.error = error
        step.completed_at = now_iso()
        self._save_step(step)
        return step

    def add_tool_call(
        self,
        task_id: str,
        step_id: str,
        tool_name: str,
        provider: str = "",
        status: str = "ok",
        input_summary: str = "",
        output_summary: str = "",
        error: str = "",
        latency_ms: int = 0,
    ) -> ToolCallRecord:
        record = ToolCallRecord(
            call_id=str(uuid.uuid4()),
            task_id=task_id,
            step_id=step_id,
            provider=provider,
            tool_name=tool_name,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            error=error,
            latency_ms=latency_ms,
        )
        self._save_tool_call(record)
        return record

    def get_task(self, task_id: str) -> Optional[OrchestrationTask]:
        if SQLMODEL_AVAILABLE:
            with Session(self._engine) as session:
                return session.get(OrchestrationTask, task_id)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM orchestration_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        finally:
            self._close(conn)
        return OrchestrationTask(**dict(row)) if row else None

    def get_step(self, step_id: str) -> Optional[OrchestrationStep]:
        if SQLMODEL_AVAILABLE:
            with Session(self._engine) as session:
                return session.get(OrchestrationStep, step_id)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM orchestration_steps WHERE step_id = ?",
                (step_id,),
            ).fetchone()
        finally:
            self._close(conn)
        return OrchestrationStep(**dict(row)) if row else None

    def list_steps(self, task_id: str) -> list[dict[str, Any]]:
        if SQLMODEL_AVAILABLE:
            with Session(self._engine) as session:
                steps = session.exec(
                    select(OrchestrationStep)
                    .where(OrchestrationStep.task_id == task_id)
                    .order_by(OrchestrationStep.sequence)
                ).all()
            return [self._to_dict(step) for step in steps]
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM orchestration_steps
                WHERE task_id = ?
                ORDER BY sequence ASC
                """,
                (task_id,),
            ).fetchall()
        finally:
            self._close(conn)
        return [dict(row) for row in rows]

    def list_tool_calls(self, task_id: str) -> list[dict[str, Any]]:
        if SQLMODEL_AVAILABLE:
            with Session(self._engine) as session:
                records = session.exec(
                    select(ToolCallRecord)
                    .where(ToolCallRecord.task_id == task_id)
                    .order_by(ToolCallRecord.created_at)
                ).all()
            return [self._to_dict(record) for record in records]
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM tool_call_records
                WHERE task_id = ?
                ORDER BY created_at ASC
                """,
                (task_id,),
            ).fetchall()
        finally:
            self._close(conn)
        return [dict(row) for row in rows]

    def get_task_payload(self, task_id: str) -> Optional[dict[str, Any]]:
        task = self.get_task(task_id)
        if not task:
            return None
        payload = self._to_dict(task)
        payload["steps"] = self.list_steps(task_id)
        payload["tool_calls"] = self.list_tool_calls(task_id)
        return payload

    def _save_task(self, task: OrchestrationTask) -> None:
        if SQLMODEL_AVAILABLE:
            with Session(self._engine) as session:
                session.merge(task)
                session.commit()
            return
        data = self._to_dict(task)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO orchestration_tasks (
                    task_id, trace_id, session_id, user_id, intent, status,
                    risk_level, user_input, final_output, error, created_at, updated_at
                ) VALUES (
                    :task_id, :trace_id, :session_id, :user_id, :intent, :status,
                    :risk_level, :user_input, :final_output, :error, :created_at, :updated_at
                )
                ON CONFLICT(task_id) DO UPDATE SET
                    intent = excluded.intent,
                    status = excluded.status,
                    risk_level = excluded.risk_level,
                    final_output = excluded.final_output,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                data,
            )
            conn.commit()
        finally:
            self._close(conn)

    def _save_step(self, step: OrchestrationStep) -> None:
        if SQLMODEL_AVAILABLE:
            with Session(self._engine) as session:
                session.merge(step)
                session.commit()
            return
        data = self._to_dict(step)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO orchestration_steps (
                    step_id, task_id, parent_step_id, sequence, name, role,
                    status, input_json, output_json, error, started_at, completed_at
                ) VALUES (
                    :step_id, :task_id, :parent_step_id, :sequence, :name, :role,
                    :status, :input_json, :output_json, :error, :started_at, :completed_at
                )
                ON CONFLICT(step_id) DO UPDATE SET
                    status = excluded.status,
                    output_json = excluded.output_json,
                    error = excluded.error,
                    completed_at = excluded.completed_at
                """,
                data,
            )
            conn.commit()
        finally:
            self._close(conn)

    def _save_tool_call(self, record: ToolCallRecord) -> None:
        if SQLMODEL_AVAILABLE:
            with Session(self._engine) as session:
                session.add(record)
                session.commit()
            return
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO tool_call_records (
                    call_id, task_id, step_id, provider, tool_name, status,
                    latency_ms, input_summary, output_summary, error, created_at
                ) VALUES (
                    :call_id, :task_id, :step_id, :provider, :tool_name, :status,
                    :latency_ms, :input_summary, :output_summary, :error, :created_at
                )
                """,
                self._to_dict(record),
            )
            conn.commit()
        finally:
            self._close(conn)

    def _init_sqlite(self) -> None:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orchestration_tasks (
                task_id TEXT PRIMARY KEY,
                trace_id TEXT,
                session_id TEXT,
                user_id TEXT,
                intent TEXT,
                status TEXT,
                risk_level TEXT,
                user_input TEXT,
                final_output TEXT,
                error TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_orchestration_task_trace
                ON orchestration_tasks(trace_id);

            CREATE TABLE IF NOT EXISTS orchestration_steps (
                step_id TEXT PRIMARY KEY,
                task_id TEXT,
                parent_step_id TEXT,
                sequence INTEGER,
                name TEXT,
                role TEXT,
                status TEXT,
                input_json TEXT,
                output_json TEXT,
                error TEXT,
                started_at TEXT,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_orchestration_step_task
                ON orchestration_steps(task_id);

            CREATE TABLE IF NOT EXISTS tool_call_records (
                call_id TEXT PRIMARY KEY,
                task_id TEXT,
                step_id TEXT,
                provider TEXT,
                tool_name TEXT,
                status TEXT,
                latency_ms INTEGER,
                input_summary TEXT,
                output_summary TEXT,
                error TEXT,
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tool_call_task
                ON tool_call_records(task_id);
            """
        )
        conn.commit()
        self._close(conn)

    def _connect(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(self.db_path)
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn: sqlite3.Connection) -> None:
        if self.db_path != ":memory:":
            conn.close()

    def _to_dict(self, obj: Any) -> dict[str, Any]:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if is_dataclass(obj):
            return asdict(obj)
        return dict(obj)
