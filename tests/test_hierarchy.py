"""
Hierarchical Orchestrator tests.
"""

import pytest

from law_agent.audit import AuditLogger
from law_agent.hierarchy import OrchestrationStore, RootOrchestrator, WorkflowPlanner
from law_agent.intent import IntentRecognizer, IntentResult, IntentType
from law_agent.orchestrator import LawOrchestrator
from law_agent.risk import RiskLabeler
from law_agent.sub_agents import DocumentAgent, ResearchAgent
from law_agent.tools import ToolRegistry


class FakeRAGClient:
    async def search_regulations(self, *args, **kwargs):
        return []

    async def search_cases(self, *args, **kwargs):
        return []

    async def search_clauses(self, *args, **kwargs):
        return []

    async def get_document_by_id(self, *args, **kwargs):
        return None


def make_root_orchestrator():
    rag_client = FakeRAGClient()
    legacy = LawOrchestrator(
        llm_client=None,
        tool_registry=ToolRegistry(),
        intent_recognizer=IntentRecognizer(),
        risk_labeler=RiskLabeler(),
        audit_logger=AuditLogger(":memory:"),
        research_agent=ResearchAgent(rag_client),
        document_agent=DocumentAgent(),
    )
    store = OrchestrationStore(":memory:")
    return RootOrchestrator(legacy, store), store


def test_workflow_planner_maps_intents_to_supervisors():
    planner = WorkflowPlanner()

    regulation = planner.plan(IntentType.REGULATION_QUERY)
    document = planner.plan(IntentType.DOCUMENT_DRAFT)

    assert regulation[0].role == "research_supervisor"
    assert regulation[0].name == "research.regulation_query"
    assert document[0].role == "document_supervisor"
    assert document[0].name == "document.draft"


def test_orchestration_store_records_task_steps_and_tool_calls():
    store = OrchestrationStore(":memory:")
    task = store.create_task(
        task_id="task_1",
        trace_id="trace_1",
        session_id="session_1",
        user_id="user_1",
        user_input="查法规",
    )
    step = store.add_step(
        task_id=task.task_id,
        name="intent.recognize",
        role="root_orchestrator",
        sequence=1,
    )
    store.add_tool_call(
        task_id=task.task_id,
        step_id=step.step_id,
        provider="research",
        tool_name="research.search_regulations",
    )
    store.finish_step(step.step_id, output_data={"intent": "regulation_query"})
    store.update_task(task.task_id, status="completed", intent="regulation_query")

    payload = store.get_task_payload("task_1")

    assert payload["status"] == "completed"
    assert payload["steps"][0]["name"] == "intent.recognize"
    assert payload["tool_calls"][0]["tool_name"] == "research.search_regulations"


@pytest.mark.asyncio
async def test_root_orchestrator_preserves_process_result_and_records_steps():
    root, store = make_root_orchestrator()

    result = await root.process("公司拖欠工资三个月，员工是否可以立即解除劳动合同？")
    payload = store.get_task_payload(result.task_id)

    assert result.success is True
    assert result.intent == IntentType.REGULATION_QUERY
    assert payload["status"] == "completed"
    assert [step["name"] for step in payload["steps"]] == [
        "intent.recognize",
        "profile.match_strategy",
        "research.regulation_query",
        "risk.review_gate",
        "risk.label",
    ]
    assert any(
        call["tool_name"] == "research.search_regulations"
        for call in payload["tool_calls"]
    )


@pytest.mark.asyncio
async def test_root_orchestrator_records_failed_step_and_task_status():
    root, store = make_root_orchestrator()

    class FakeIntentRecognizer:
        async def recognize(self, user_input):
            return IntentResult(intent=IntentType.GENERAL, confidence=0.9)

    async def fail_general(user_input, context):
        context.tools_used.append("llm.generate_general_answer")
        raise RuntimeError("llm offline")

    root.legacy.intent_recognizer = FakeIntentRecognizer()
    root.legacy._handle_general = fail_general

    result = await root.process("随便聊聊")
    payload = store.get_task_payload(result.task_id)

    assert result.success is False
    assert payload["status"] == "failed"
    assert payload["error"] == "llm offline"
    assert any(step["status"] == "failed" for step in payload["steps"])
