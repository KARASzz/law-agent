"""
SQLModel adapter tests for legacy storage classes.
"""

import sqlite3

import pytest

from law_agent.audit import AuditLog, AuditLogger
from law_agent.client_profiles import ClientProfileStore
from law_agent.review import ReviewTaskStore


pytest.importorskip("sqlmodel")


@pytest.mark.asyncio
async def test_audit_logger_sqlmodel_adapter_reads_legacy_sqlite_file(tmp_path):
    db_path = tmp_path / "audit.db"
    legacy = AuditLogger(str(db_path))
    await legacy.log(
        AuditLog(
            task_id="task_1",
            session_id="session_1",
            trace_id="trace_1",
            user_id="user_1",
            intent="document_draft",
            input_summary="生成起诉状",
            output_summary="草稿",
            tools_used="document.draft",
            risk_level="high",
        )
    )

    adapter = AuditLogger(str(db_path), use_sqlmodel=True)
    await adapter.set_confirmation("trace_1", True)
    action = await adapter.log_external_action(
        task_id="task_1",
        trace_id="trace_1",
        user_id="user_1",
        actor_id="lawyer_1",
        action_type="export",
        confirmed=True,
        profile_record_ids=["profile_1"],
    )

    log = await adapter.get_by_trace_id("trace_1")
    logs = await adapter.query(user_id="user_1")
    actions = await adapter.query_external_actions(trace_id="trace_1")
    stats = await adapter.get_statistics()

    assert log.confirmed is True
    assert log.exported is True
    assert logs[0].task_id == "task_1"
    assert action["profile_record_ids"] == ["profile_1"]
    assert actions[0]["action_type"] == "export"
    assert stats["total_tasks"] == 1
    assert stats["risk_stats"]["high"] == 1

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "lawyer_client_profiles" not in tables


def test_review_task_store_sqlmodel_adapter_reads_legacy_sqlite_file(tmp_path):
    db_path = tmp_path / "tasks.db"
    legacy = ReviewTaskStore(str(db_path))
    legacy.create_pending(
        trace_id="trace_1",
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
        intent="document_draft",
        risk_level="high",
        original_output="原始草稿",
        user_input="生成起诉状",
        task_title="起诉状草稿审阅",
    )

    adapter = ReviewTaskStore(str(db_path), use_sqlmodel=True)
    pending = adapter.list_tasks(review_status="pending_review")
    confirmed = adapter.confirm(
        trace_id="trace_1",
        reviewer_id="lawyer_1",
        reviewed_output="确认后草稿",
    )

    assert [task.trace_id for task in pending] == ["trace_1"]
    assert confirmed.review_status == "confirmed"
    assert confirmed.reviewed_output == "确认后草稿"
    assert adapter.get("trace_1").task_title == "起诉状草稿审阅"

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "audit_logs" not in tables


def test_client_profile_store_exposes_sqlmodel_migration_plan(tmp_path):
    store = ClientProfileStore(str(tmp_path / "profiles.db"))
    plan = store.get_sqlmodel_migration_plan()

    assert plan["status"] == "planned"
    assert plan["legacy_sqlite_compatibility"] is True
    assert plan["sqlmodel_available"] is True
    assert {item["table"] for item in plan["tables"]} == {
        "profile_import_batches",
        "lawyer_client_profiles",
        "profile_update_events",
    }
