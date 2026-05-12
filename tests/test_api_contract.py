"""
API contract tests for the FastAPI surface.
"""

import pytest

from law_agent.audit import AuditLog
from law_agent.audit import AuditLogger
from law_agent.intent import IntentType
from law_agent.intent import IntentResult
from law_agent.intent import IntentRecognizer
from law_agent.main import ExternalActionError
from law_agent.main import LawAgentApp, create_api_app
from law_agent.orchestrator import LawOrchestrator
from law_agent.orchestrator import ProcessResult
from law_agent.review import ReviewTaskStore
from law_agent.risk import RiskResult
from law_agent.risk import RiskLevel


class StubLawApp:
    async def initialize(self):
        return None

    async def shutdown(self):
        return None

    async def process(self, user_input: str, session_id: str = "", user_id: str = ""):
        return {
            "success": True,
            "task_id": "task_1",
            "trace_id": "trace_1",
            "output": user_input,
            "intent": "regulation_query",
            "risk_level": "low",
            "confidence": 0.9,
            "tools_used": [],
            "requires_human_review": False,
            "can_export": True,
            "profile_record_ids": [],
            "profile_strategy": {},
            "review_status": "not_required",
            "review_task": None,
            "processing_time": 0.01,
            "error": None,
        }

    async def research_web(self, **kwargs):
        return {
            "success": True,
            "query": kwargs["query"],
            "purpose": kwargs.get("purpose") or "quick_search",
            "answer": "联网研究结果",
            "sources": [],
            "tool_calls": [{"provider": "tavily", "tool": "search:general", "status": "ok", "count": 0}],
            "providers_used": ["tavily"],
            "warnings": [],
            "usage": {},
        }

    async def create_task(self, **kwargs):
        return {
            "task": {
                "task_id": "task_1",
                "trace_id": "trace_1",
                "status": "completed",
            },
            "result": await self.process(**kwargs),
        }

    def get_task(self, task_id: str):
        if task_id == "missing":
            return None
        return {
            "task_id": task_id,
            "trace_id": "trace_1",
            "status": "completed",
            "steps": [],
            "tool_calls": [],
        }

    def get_task_steps(self, task_id: str):
        return [{"task_id": task_id, "name": "intent.recognize"}]

    async def save_upload(self, upload_file, trace_id: str = ""):
        return {
            "filename": upload_file.filename,
            "path": "data/uploads/test.txt",
            "size": len(await upload_file.read()),
            "trace_id": trace_id,
        }

    def import_profiles(self, json_file_path: str):
        return {
            "import_id": "import_1",
            "source_file": json_file_path,
            "records_seen": 1,
            "records_upserted": 1,
            "records_skipped": 0,
            "db_path": "data/client_profiles.db",
        }

    def list_profiles(self, **kwargs):
        return [{"record_id": "profile_1", "matter_type": kwargs.get("matter_type")}]

    def get_profile(self, record_id: str):
        if record_id == "missing":
            return None
        return {"record_id": record_id}

    async def query_audit(self, **kwargs):
        return [{"trace_id": "trace_1", "risk_level": kwargs.get("risk_level")}]

    async def query_external_actions(self, **kwargs):
        return [{"trace_id": kwargs.get("trace_id"), "action_type": kwargs.get("action_type")}]

    def list_review_tasks(self, **kwargs):
        return [
            {
                "trace_id": "trace_1",
                "review_status": kwargs.get("review_status") or "pending_review",
                "risk_level": kwargs.get("risk_level") or "high",
            }
        ]

    async def confirm_review(self, **kwargs):
        return {
            "trace_id": kwargs["trace_id"],
            "review_status": "confirmed",
            "reviewer_id": kwargs["reviewer_id"],
            "reviewed_output": kwargs.get("reviewed_output"),
        }

    async def reject_review(self, **kwargs):
        return {
            "trace_id": kwargs["trace_id"],
            "review_status": "rejected",
            "reviewer_id": kwargs["reviewer_id"],
            "rejection_reason": kwargs["rejection_reason"],
        }

    async def export_output(self, **kwargs):
        return {
            "allowed": True,
            "trace_id": kwargs["trace_id"],
            "action_type": "export",
            "actor_id": kwargs["actor_id"],
            "content": "确认后内容",
        }

    async def send_output(self, **kwargs):
        return {
            "allowed": True,
            "trace_id": kwargs["trace_id"],
            "action_type": "send",
            "actor_id": kwargs["actor_id"],
        }

    class AuditLogger:
        async def get_statistics(self):
            return {"total_tasks": 0}

    audit_logger = AuditLogger()


def test_create_api_app_routes():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app = create_api_app(StubLawApp())

    with TestClient(app) as client:
        process_response = client.post(
            "/api/v1/process",
            json={"user_input": "查法规", "session_id": "s1", "user_id": "u1"},
        )
        assert process_response.status_code == 200
        payload = process_response.json()
        assert payload["requires_human_review"] is False
        assert payload["can_export"] is True
        assert payload["review_status"] == "not_required"
        assert payload["profile_record_ids"] == []

        research_response = client.post(
            "/api/v1/research/web",
            json={"query": "查最新法规", "purpose": "quick_search"},
        )
        assert research_response.status_code == 200
        assert research_response.json()["answer"] == "联网研究结果"

        task_response = client.post(
            "/api/v1/tasks",
            json={"user_input": "查法规", "session_id": "s1", "user_id": "u1"},
        )
        assert task_response.status_code == 200
        assert task_response.json()["task"]["status"] == "completed"
        assert client.get("/api/v1/tasks/task_1").status_code == 200
        assert client.get("/api/v1/tasks/task_1/steps").json()["items"][0]["name"] == "intent.recognize"
        assert client.get("/api/v1/tasks/missing").status_code == 404
        upload_response = client.post(
            "/api/v1/files/upload",
            data={"trace_id": "trace_1"},
            files={"file": ("contract.txt", b"contract body", "text/plain")},
        )
        assert upload_response.status_code == 200
        assert upload_response.json()["filename"] == "contract.txt"

        workbench_response = client.get("/workbench")
        assert workbench_response.status_code == 200
        assert "Law Agent 工作台" in workbench_response.text
        assert "层级编排" in workbench_response.text
        assert "WORKBENCH_CONFIG" in workbench_response.text
        assert "/static/js/workbench.js" in workbench_response.text
        assert client.get("/static/js/workbench.js").status_code == 200
        assert client.get("/static/css/workbench.css").status_code == 200

        assert client.get("/api/v1/profiles?matter_type=民事合同").status_code == 200
        assert client.get("/api/v1/profiles/profile_1").status_code == 200
        assert client.get("/api/v1/profiles/missing").status_code == 404
        assert client.get("/api/v1/audit?risk_level=low").status_code == 200
        assert client.get(
            "/api/v1/audit/external-actions?trace_id=trace_1&action_type=export"
        ).status_code == 200
        assert client.get(
            "/api/v1/review/tasks?review_status=pending_review"
        ).status_code == 200
        assert client.post(
            "/api/v1/review/confirm",
            json={
                "trace_id": "trace_1",
                "reviewer_id": "lawyer_1",
                "reviewed_output": "确认后内容",
            },
        ).status_code == 200
        assert client.post(
            "/api/v1/review/reject",
            json={
                "trace_id": "trace_1",
                "reviewer_id": "lawyer_1",
                "rejection_reason": "事实不足",
            },
        ).status_code == 200
        assert client.post(
            "/api/v1/export",
            json={
                "trace_id": "trace_1",
                "actor_id": "lawyer_1",
                "export_format": "markdown",
            },
        ).status_code == 200
        assert client.post(
            "/api/v1/send",
            json={
                "trace_id": "trace_1",
                "actor_id": "lawyer_1",
                "destination": "client@example.com",
            },
        ).status_code == 200


@pytest.mark.asyncio
async def test_law_agent_app_process_exposes_review_fields():
    class FakeOrchestrator:
        async def process(self, **kwargs):
            return ProcessResult(
                success=True,
                task_id="task_1",
                trace_id="trace_1",
                output="ok",
                intent=IntentType.DOCUMENT_DRAFT,
                risk_level=RiskLevel.HIGH,
                confidence=0.8,
                tools_used=["document.generate_draft"],
                requires_human_review=True,
                can_export=False,
                profile_record_ids=["profile_1"],
                profile_strategy={"strategy_choice": "证据先行"},
                review_status="pending_review",
            )

    class FakeReviewTask:
        def to_dict(self):
            return {"trace_id": "trace_1", "review_status": "pending_review"}

    class FakeReviewStore:
        def __init__(self):
            self.created = None

        def create_pending(self, **kwargs):
            self.created = kwargs
            return FakeReviewTask()

    app = LawAgentApp.__new__(LawAgentApp)
    app._initialized = True
    app.orchestrator = FakeOrchestrator()
    app.review_store = FakeReviewStore()

    result = await app.process("生成起诉状")

    assert result["requires_human_review"] is True
    assert result["can_export"] is False
    assert result["profile_record_ids"] == ["profile_1"]
    assert result["profile_strategy"]["strategy_choice"] == "证据先行"
    assert result["review_status"] == "pending_review"
    assert result["review_task"]["review_status"] == "pending_review"
    assert app.review_store.created["risk_level"] == "high"


@pytest.mark.asyncio
async def test_law_agent_app_review_tasks_include_runtime_from_audit():
    class FakeLLM:
        async def call(self, prompt, **kwargs):
            return "咨询工作台能力"

    audit_logger = AuditLogger(":memory:")
    review_store = ReviewTaskStore(":memory:")
    await audit_logger.log(
        AuditLog(
            task_id="task_1",
            session_id="session_1",
            trace_id="trace_1",
            user_id="user_1",
            intent="general",
            input_summary="你好",
            output_summary="LLM 答复",
            tools_used="llm.generate_general_answer",
            risk_level="medium",
        )
    )
    review_store.create_pending(
        trace_id="trace_1",
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
        intent="general",
        risk_level="medium",
        original_output="LLM 答复",
    )

    app = LawAgentApp.__new__(LawAgentApp)
    app.config = type(
        "Config",
        (),
        {
            "llm": type(
                "LLMConfig",
                (),
                {
                    "model": "MiniMax-M2.7",
                    "fallback_models": [],
                },
            )()
        },
    )()
    app.llm_client = FakeLLM()
    app.audit_logger = audit_logger
    app.review_store = review_store

    items = await app.list_review_tasks()

    assert items[0]["tools_used"] == ["llm.generate_general_answer"]
    assert items[0]["user_input"] == "你好"
    assert items[0]["task_title"] == "咨询工作台能力"
    assert items[0]["llm_enabled"] is True
    assert items[0]["llm_status"] == "called"
    assert items[0]["llm_model"] == "MiniMax-M2.7"
    assert items[0]["llm_fallback_models"] == []


@pytest.mark.asyncio
async def test_orchestrator_audit_uses_input_and_output_summaries():
    class FakeIntentRecognizer:
        async def recognize(self, user_input):
            return IntentResult(intent=IntentType.GENERAL, confidence=0.9)

    class FakeRiskLabeler:
        async def label_detailed(self, intent, content, metadata=None):
            return RiskResult(level=RiskLevel.LOW, message="ok")

    class FakeAuditLogger:
        def __init__(self):
            self.log_entry = None

        async def log(self, audit_log):
            self.log_entry = audit_log

    audit_logger = FakeAuditLogger()
    orchestrator = LawOrchestrator(
        llm_client=None,
        tool_registry=None,
        intent_recognizer=FakeIntentRecognizer(),
        risk_labeler=FakeRiskLabeler(),
        audit_logger=audit_logger,
        research_agent=None,
        document_agent=None,
    )

    result = await orchestrator.process("这是用户原始输入", session_id="s1", user_id="u1")

    assert result.success is True
    assert audit_logger.log_entry.input_summary == "这是用户原始输入"
    assert audit_logger.log_entry.output_summary.startswith("我收到了您的问题")


@pytest.mark.asyncio
async def test_orchestrator_uses_llm_for_general_unknown_input():
    class FakeLLM:
        def __init__(self):
            self.calls = []

        async def call(self, prompt, **kwargs):
            self.calls.append(prompt)
            return "这是 LLM 生成的通用答复"

    class FakeRiskLabeler:
        async def label_detailed(self, intent, content, metadata=None):
            return RiskResult(level=RiskLevel.LOW, message="ok")

    class FakeAuditLogger:
        async def log(self, audit_log):
            self.log_entry = audit_log

    llm = FakeLLM()
    audit_logger = FakeAuditLogger()
    orchestrator = LawOrchestrator(
        llm_client=llm,
        tool_registry=None,
        intent_recognizer=IntentRecognizer(llm),
        risk_labeler=FakeRiskLabeler(),
        audit_logger=audit_logger,
        research_agent=None,
        document_agent=None,
    )

    result = await orchestrator.process("随便聊聊这个系统")

    assert result.output == "这是 LLM 生成的通用答复"
    assert result.intent == IntentType.GENERAL
    assert "llm.generate_general_answer" in result.tools_used
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_orchestrator_applies_profile_strategy_to_output_and_result():
    class FakeIntentRecognizer:
        async def recognize(self, user_input):
            return IntentResult(intent=IntentType.REGULATION_QUERY, confidence=0.9)

    class FakeRiskLabeler:
        async def label_detailed(self, intent, content, metadata=None):
            return RiskResult(level=RiskLevel.LOW, message="ok")

    class FakeResearchAgent:
        async def search_regulations(self, query, context):
            return "法规回答"

    class FakeAuditLogger:
        async def log(self, audit_log):
            self.log_entry = audit_log

    class FakeProfileStore:
        def __init__(self):
            self.seen_kwargs = None

        def list_driver_profiles(self, **kwargs):
            self.seen_kwargs = kwargs
            assert kwargs["matter_type"] == "民事合同"
            return [
                {
                    "record_id": "profile_1",
                    "first_judgment": "需补证据",
                    "strategy_choice": "证据先行",
                    "risk_communication": "直说高风险",
                    "handling_temperature": "冷静理性",
                    "reusable_rule": "合同争议先补证据。",
                }
            ]

    audit_logger = FakeAuditLogger()
    profile_store = FakeProfileStore()
    orchestrator = LawOrchestrator(
        llm_client=None,
        tool_registry=None,
        intent_recognizer=FakeIntentRecognizer(),
        risk_labeler=FakeRiskLabeler(),
        audit_logger=audit_logger,
        research_agent=FakeResearchAgent(),
        document_agent=None,
        client_profile_store=profile_store,
    )

    result = await orchestrator.process("合同纠纷证据不足，是否可以起诉并追回欠款")

    assert profile_store.seen_kwargs["client_goal"] == "回款"
    assert profile_store.seen_kwargs["first_judgment"] == "需补证据"
    assert result.profile_record_ids == ["profile_1"]
    assert result.profile_strategy["strategy_choice"] == "证据先行"
    assert "不宜直接生成对外法律意见" in result.profile_strategy["external_document_suitability"]
    assert "## 【画像策略】" in result.output
    assert "对外文书适用性" in result.output
    assert "client_profiles.match_driver_profiles" in result.tools_used


@pytest.mark.asyncio
async def test_external_action_requires_confirmed_review_and_logs_details():
    audit_logger = AuditLogger(":memory:")
    review_store = ReviewTaskStore(":memory:")
    await audit_logger.log(
        AuditLog(
            task_id="task_1",
            session_id="session_1",
            trace_id="trace_1",
            user_id="user_1",
            intent="document_draft",
            input_summary="生成起诉状",
            output_summary="原始草稿摘要",
            tools_used="document.generate_draft,client_profile:profile_1",
            risk_level="high",
        )
    )
    review_store.create_pending(
        trace_id="trace_1",
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
        intent="document_draft",
        risk_level="high",
        original_output="确认前草稿",
    )

    app = LawAgentApp.__new__(LawAgentApp)
    app.audit_logger = audit_logger
    app.review_store = review_store

    with pytest.raises(ExternalActionError):
        await app.export_output(
            trace_id="trace_1",
            actor_id="lawyer_1",
            destination="case-folder",
        )

    review_store.confirm(
        trace_id="trace_1",
        reviewer_id="lawyer_1",
        reviewed_output="确认后草稿",
    )
    await audit_logger.set_confirmation("trace_1", True)

    result = await app.export_output(
        trace_id="trace_1",
        actor_id="assistant_1",
        export_format="markdown",
        destination="case-folder",
    )

    assert result["allowed"] is True
    assert result["content"] == "确认后草稿"
    assert result["reviewer_id"] == "lawyer_1"
    assert result["profile_record_ids"] == ["profile_1"]

    actions = await audit_logger.query_external_actions(trace_id="trace_1")
    assert actions[0]["actor_id"] == "assistant_1"
    assert actions[0]["reviewer_id"] == "lawyer_1"
    assert actions[0]["original_output"] == "确认前草稿"
    assert actions[0]["final_output"] == "确认后草稿"
    assert actions[0]["profile_record_ids"] == ["profile_1"]

    logs = await audit_logger.query(user_id="user_1")
    assert logs[0].confirmed is True
    assert logs[0].exported is True
