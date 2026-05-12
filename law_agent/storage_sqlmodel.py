"""SQLModel records shared by storage adapters.

The legacy stores still own the public API.  These records mirror the existing
SQLite table names so new SQLModel sessions can read and write the same files
during the migration window.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - exercised when sqlmodel is installed
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Field, SQLModel, create_engine

    SQLMODEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    Field = None
    SQLModel = None
    StaticPool = None
    create_engine = None
    SQLMODEL_AVAILABLE = False


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_sqlite_engine(db_path: str):
    """Create a SQLModel SQLite engine for a legacy DB path."""
    if not SQLMODEL_AVAILABLE:
        raise RuntimeError("sqlmodel is not installed")

    if db_path == ":memory:":
        return create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


def create_storage_tables(engine, models: Optional[list[type]] = None) -> None:
    if not SQLMODEL_AVAILABLE:
        raise RuntimeError("sqlmodel is not installed")
    tables = [model.__table__ for model in models] if models else None
    SQLModel.metadata.create_all(engine, tables=tables)


if SQLMODEL_AVAILABLE:

    class AuditLogRecord(SQLModel, table=True):
        __tablename__ = "audit_logs"

        id: Optional[int] = Field(default=None, primary_key=True)
        task_id: str = Field(index=True)
        session_id: str = Field(default="", index=True)
        trace_id: str = Field(index=True, sa_column_kwargs={"unique": True})
        user_id: str = Field(default="", index=True)
        intent: str = Field(index=True)
        input_summary: str = ""
        output_summary: str = ""
        tools_used: str = ""
        risk_level: str = Field(default="", index=True)
        confirmed: int = 0
        exported: int = 0
        log_level: str = "info"
        error_message: Optional[str] = None
        timestamp: str = Field(default_factory=now_iso, index=True)

    class ExportLogRecord(SQLModel, table=True):
        __tablename__ = "export_logs"

        id: Optional[int] = Field(default=None, primary_key=True)
        task_id: str
        trace_id: str = Field(index=True, sa_column_kwargs={"unique": True})
        user_id: str
        export_type: str = "document"
        export_format: str = "markdown"
        confirmed: int = 0
        timestamp: str = Field(default_factory=now_iso)

    class ExternalActionLogRecord(SQLModel, table=True):
        __tablename__ = "external_action_logs"

        id: Optional[int] = Field(default=None, primary_key=True)
        task_id: str
        trace_id: str = Field(index=True)
        user_id: str = Field(default="", index=True)
        actor_id: str
        action_type: str = Field(index=True)
        export_format: str = "markdown"
        destination: str = ""
        risk_level: str = ""
        review_status: str = "not_required"
        confirmed: int = 0
        reviewer_id: Optional[str] = None
        reviewed_at: Optional[str] = None
        original_output: str = ""
        final_output: str = ""
        profile_record_ids: str = ""
        timestamp: str = Field(default_factory=now_iso)

    class ReviewTaskRecord(SQLModel, table=True):
        __tablename__ = "review_tasks"

        trace_id: str = Field(primary_key=True)
        task_id: str
        session_id: str = ""
        user_id: str = Field(default="", index=True)
        intent: str
        risk_level: str = Field(index=True)
        review_status: str = Field(index=True)
        original_output: str
        user_input: Optional[str] = None
        task_title: Optional[str] = None
        reviewed_output: Optional[str] = None
        reviewer_id: Optional[str] = None
        reviewed_at: Optional[str] = None
        rejection_reason: Optional[str] = None
        created_at: str
        updated_at: str

    class ProfileImportBatchRecord(SQLModel, table=True):
        __tablename__ = "profile_import_batches"

        import_id: str = Field(primary_key=True)
        schema_version: Optional[str] = None
        generated_at: Optional[str] = None
        input_file: Optional[str] = None
        input_file_sha256: Optional[str] = None
        json_file_path: str
        json_file_sha256: str
        stats_json: str
        imported_at: str

    class LawyerClientProfileRecord(SQLModel, table=True):
        __tablename__ = "lawyer_client_profiles"

        record_id: str = Field(primary_key=True)
        latest_import_id: str = Field(index=True)
        source_file: Optional[str] = None
        source_file_sha256: Optional[str] = None
        sheet_name: Optional[str] = None
        excel_row_number: Optional[int] = None
        data_source: Optional[str] = None
        matter_type: Optional[str] = Field(default=None, index=True)
        stage: Optional[str] = Field(default=None, index=True)
        representativeness: Optional[str] = None
        conflict_structure: Optional[str] = None
        role_pattern: Optional[str] = None
        client_goal: Optional[str] = Field(default=None, index=True)
        key_constraints: Optional[str] = None
        first_judgment: Optional[str] = Field(default=None, index=True)
        abstract_reason: Optional[str] = None
        strategy_choice: Optional[str] = None
        value_order: Optional[str] = None
        risk_communication: Optional[str] = None
        handling_temperature: Optional[str] = None
        reusable_rule: Optional[str] = None
        collection_date: Optional[str] = None
        collection_ref: Optional[str] = None
        result_review: Optional[str] = None
        note: Optional[str] = None
        desensitization_status: Optional[str] = None
        ingestion_level: Optional[str] = Field(default=None, index=True)
        cleaning_note: Optional[str] = None
        review_tag: Optional[str] = None
        profile_update_action: Optional[str] = None
        missing_core_fields_json: str
        privacy_decision: Optional[str] = None
        sensitive_flags_json: str
        sensitive_flags_by_field_json: str
        raw_record_json: str
        created_at: str
        updated_at: str

    class ProfileUpdateEventRecord(SQLModel, table=True):
        __tablename__ = "profile_update_events"

        id: Optional[int] = Field(default=None, primary_key=True)
        record_id: str = Field(index=True)
        import_id: str = Field(index=True)
        profile_update_action: Optional[str] = None
        review_tag: Optional[str] = None
        ingestion_level: Optional[str] = None
        collection_date: Optional[str] = None
        created_at: str

else:
    AuditLogRecord = None
    ExportLogRecord = None
    ExternalActionLogRecord = None
    ReviewTaskRecord = None
    ProfileImportBatchRecord = None
    LawyerClientProfileRecord = None
    ProfileUpdateEventRecord = None


CLIENT_PROFILE_SQLMODEL_MIGRATION_PLAN = {
    "status": "planned",
    "legacy_sqlite_compatibility": True,
    "tables": [
        {
            "table": "profile_import_batches",
            "model": "ProfileImportBatchRecord",
            "phase": "batch metadata read/write parity",
        },
        {
            "table": "lawyer_client_profiles",
            "model": "LawyerClientProfileRecord",
            "phase": "profile query parity before ingestion rewrite",
        },
        {
            "table": "profile_update_events",
            "model": "ProfileUpdateEventRecord",
            "phase": "event append parity after profile query parity",
        },
    ],
    "migration_steps": [
        "Keep current SQLite schema as the source of truth during MVP.",
        "Introduce SQLModel read adapters for profile queries.",
        "Switch import batch and profile upserts after parity tests pass.",
        "Move JSON fields to typed columns only after API consumers stop reading raw_record_json.",
    ],
}
