"""把意图转换为层级工作流步骤。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from law_agent.intent import IntentType


@dataclass(frozen=True)
class WorkflowStepSpec:
    name: str
    role: str


class WorkflowPlanner:
    """MVP 版确定性 planner。"""

    def plan(self, intent: IntentType) -> List[WorkflowStepSpec]:
        if intent == IntentType.REGULATION_QUERY:
            return [
                WorkflowStepSpec("research.regulation_query", "research_supervisor"),
                WorkflowStepSpec("risk.review_gate", "review_supervisor"),
            ]
        if intent == IntentType.CASE_SEARCH:
            return [
                WorkflowStepSpec("research.case_search", "research_supervisor"),
                WorkflowStepSpec("risk.review_gate", "review_supervisor"),
            ]
        if intent == IntentType.DOCUMENT_DRAFT:
            return [
                WorkflowStepSpec("document.draft", "document_supervisor"),
                WorkflowStepSpec("risk.review_gate", "review_supervisor"),
            ]
        if intent == IntentType.CONTRACT_REVIEW:
            return [
                WorkflowStepSpec("document.contract_review", "document_supervisor"),
                WorkflowStepSpec("research.contract_clauses", "research_supervisor"),
                WorkflowStepSpec("risk.review_gate", "review_supervisor"),
            ]
        return [
            WorkflowStepSpec("general.answer", "general_supervisor"),
            WorkflowStepSpec("risk.review_gate", "review_supervisor"),
        ]
