"""领域主管层，负责把 planner 步骤分派给现有 Worker Agent。"""

from __future__ import annotations

from typing import Any

from .models import AgentResult


class ResearchSupervisor:
    """研究主管：法规、类案、合同条款和联网补强。"""

    def __init__(self, legacy_orchestrator: Any):
        self.legacy = legacy_orchestrator

    async def handle(self, step_name: str, user_input: str, context: Any) -> AgentResult:
        if step_name == "research.regulation_query":
            content = await self.legacy._handle_regulation_query(user_input, context)
            return AgentResult(content=content)
        if step_name == "research.case_search":
            content = await self.legacy._handle_case_search(user_input, context)
            return AgentResult(content=content)
        if step_name == "research.contract_clauses":
            content = await self.legacy._handle_contract_review(user_input, context)
            return AgentResult(content=content)
        return AgentResult(content="")


class DocumentSupervisor:
    """文书主管：文书初稿和合同文本初筛。"""

    def __init__(self, legacy_orchestrator: Any):
        self.legacy = legacy_orchestrator

    async def handle(self, step_name: str, user_input: str, context: Any) -> AgentResult:
        if step_name == "document.draft":
            content = await self.legacy._handle_document_draft(user_input, context)
            return AgentResult(content=content, requires_review=True)
        if step_name == "document.contract_review":
            context.tools_used.append("document.contract_review_prefilter")
            content = await self.legacy.document.review_contract(user_input, context)
            return AgentResult(content=content)
        return AgentResult(content="")


class ReviewSupervisor:
    """审阅主管占位：保留风险门禁步骤，实际风险分级由 RootOrchestrator 统一执行。"""

    async def handle(self, step_name: str, user_input: str, context: Any) -> AgentResult:
        return AgentResult(
            content="风险门禁将在最终输出生成后统一评估。",
            metadata={"step": step_name},
        )


class SupervisorOrchestrator:
    """按 role 分派给领域主管。"""

    def __init__(
        self,
        research: ResearchSupervisor,
        document: DocumentSupervisor,
        review: ReviewSupervisor,
        legacy_orchestrator: Any,
    ):
        self.research = research
        self.document = document
        self.review = review
        self.legacy = legacy_orchestrator

    async def execute(self, role: str, step_name: str, user_input: str, context: Any) -> AgentResult:
        if role == "research_supervisor":
            return await self.research.handle(step_name, user_input, context)
        if role == "document_supervisor":
            return await self.document.handle(step_name, user_input, context)
        if role == "review_supervisor":
            return await self.review.handle(step_name, user_input, context)
        if role == "general_supervisor":
            content = await self.legacy._handle_general(user_input, context)
            return AgentResult(content=content)
        return AgentResult(content="")
