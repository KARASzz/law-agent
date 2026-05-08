"""
Shared test fixtures.
"""

import pytest

from law_agent.audit import AuditLogger
from law_agent.intent import IntentRecognizer
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


@pytest.fixture
def orchestrator():
    rag_client = FakeRAGClient()
    return LawOrchestrator(
        llm_client=None,
        tool_registry=ToolRegistry(),
        intent_recognizer=IntentRecognizer(),
        risk_labeler=RiskLabeler(),
        audit_logger=AuditLogger(":memory:"),
        research_agent=ResearchAgent(rag_client),
        document_agent=DocumentAgent(),
    )
