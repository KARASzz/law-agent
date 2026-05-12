"""Hierarchical Orchestrator 的任务、步骤和工具调用模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field as PydanticField

try:  # pragma: no cover - 当前测试环境可能尚未安装 sqlmodel
    from sqlmodel import Field, SQLModel

    SQLMODEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    Field = None
    SQLModel = None
    SQLMODEL_AVAILABLE = False


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class AgentResult(BaseModel):
    """Supervisor/Worker 的统一输出。"""

    content: str = ""
    sources: list[dict[str, Any]] = PydanticField(default_factory=list)
    requires_review: bool = False
    metadata: dict[str, Any] = PydanticField(default_factory=dict)


if SQLMODEL_AVAILABLE:

    class OrchestrationTask(SQLModel, table=True):
        """一次用户请求对应的根任务。"""

        __tablename__ = "orchestration_tasks"

        task_id: str = Field(primary_key=True)
        trace_id: str = Field(index=True)
        session_id: str = ""
        user_id: str = ""
        intent: str = "unknown"
        status: str = "pending"
        risk_level: str = "unknown"
        user_input: str = ""
        final_output: str = ""
        error: str = ""
        created_at: str = Field(default_factory=now_iso)
        updated_at: str = Field(default_factory=now_iso)

    class OrchestrationStep(SQLModel, table=True):
        """层级编排中的一个执行步骤。"""

        __tablename__ = "orchestration_steps"

        step_id: str = Field(primary_key=True)
        task_id: str = Field(index=True)
        parent_step_id: Optional[str] = Field(default=None, index=True)
        sequence: int = 0
        name: str
        role: str
        status: str = "pending"
        input_json: str = ""
        output_json: str = ""
        error: str = ""
        started_at: str = Field(default_factory=now_iso)
        completed_at: str = ""

    class ToolCallRecord(SQLModel, table=True):
        """结构化工具调用记录。"""

        __tablename__ = "tool_call_records"

        call_id: str = Field(primary_key=True)
        task_id: str = Field(index=True)
        step_id: str = Field(index=True)
        provider: str = ""
        tool_name: str
        status: str = "ok"
        latency_ms: int = 0
        input_summary: str = ""
        output_summary: str = ""
        error: str = ""
        created_at: str = Field(default_factory=now_iso)

else:

    @dataclass
    class OrchestrationTask:
        task_id: str
        trace_id: str
        session_id: str = ""
        user_id: str = ""
        intent: str = "unknown"
        status: str = "pending"
        risk_level: str = "unknown"
        user_input: str = ""
        final_output: str = ""
        error: str = ""
        created_at: str = field(default_factory=now_iso)
        updated_at: str = field(default_factory=now_iso)

    @dataclass
    class OrchestrationStep:
        step_id: str
        task_id: str
        parent_step_id: Optional[str] = None
        sequence: int = 0
        name: str = ""
        role: str = ""
        status: str = "pending"
        input_json: str = ""
        output_json: str = ""
        error: str = ""
        started_at: str = field(default_factory=now_iso)
        completed_at: str = ""

    @dataclass
    class ToolCallRecord:
        call_id: str
        task_id: str
        step_id: str
        provider: str = ""
        tool_name: str = ""
        status: str = "ok"
        latency_ms: int = 0
        input_summary: str = ""
        output_summary: str = ""
        error: str = ""
        created_at: str = field(default_factory=now_iso)
