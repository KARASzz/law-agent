"""RootOrchestrator：Hierarchical 模式的根编排器。"""

from __future__ import annotations

import time
from typing import Any, List

from loguru import logger

from law_agent.intent import IntentType
from law_agent.orchestrator import ProcessingContext, ProcessResult
from law_agent.risk import RiskLevel

from .models import AgentResult
from .planner import WorkflowPlanner
from .store import OrchestrationStore
from .supervisors import (
    DocumentSupervisor,
    ResearchSupervisor,
    ReviewSupervisor,
    SupervisorOrchestrator,
)


class RootOrchestrator:
    """
    Hierarchical 根编排器。

    v1 复用现有 LawOrchestrator 的 intent/profile/risk/audit 辅助逻辑，
    把原来的 if/elif 分支迁移到 planner + supervisor + step store。
    """

    def __init__(
        self,
        legacy_orchestrator: Any,
        store: OrchestrationStore,
        planner: WorkflowPlanner | None = None,
        supervisor: SupervisorOrchestrator | None = None,
    ):
        self.legacy = legacy_orchestrator
        self.store = store
        self.planner = planner or WorkflowPlanner()
        self.supervisor = supervisor or SupervisorOrchestrator(
            research=ResearchSupervisor(legacy_orchestrator),
            document=DocumentSupervisor(legacy_orchestrator),
            review=ReviewSupervisor(),
            legacy_orchestrator=legacy_orchestrator,
        )

    async def process(
        self,
        user_input: str,
        session_id: str = "",
        user_id: str = "",
    ) -> ProcessResult:
        context = ProcessingContext(
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
        )
        task = self.store.create_task(
            task_id=context.request_id,
            trace_id=context.trace_id,
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
        )
        start_time = time.time()

        try:
            await self._recognize_intent(user_input, context)
            self._apply_profile(user_input, context)

            if context.confidence < 0.5 and not self.legacy.llm:
                output = self.legacy.unknown_intent_response
            else:
                if context.confidence < 0.5:
                    context.intent = IntentType.GENERAL
                output = await self._execute_workflow(user_input, context)
                output = self.legacy._append_profile_strategy(output, context)

            context.final_output = output
            await self._label_risk(context, output)

            processing_time = time.time() - start_time
            self.store.update_task(
                task.task_id,
                status="completed",
                intent=context.intent.value if context.intent else "unknown",
                risk_level=context.risk_level.value if context.risk_level else "unknown",
                final_output=output,
            )
            return ProcessResult(
                success=True,
                task_id=context.request_id,
                trace_id=context.trace_id,
                output=output,
                intent=context.intent,
                risk_level=context.risk_level,
                confidence=context.confidence,
                tools_used=context.tools_used,
                requires_human_review=context.requires_human_review,
                can_export=context.can_export,
                profile_record_ids=context.profile_record_ids,
                profile_strategy=context.profile_strategy,
                review_status=context.review_status,
                processing_time=processing_time,
            )
        except Exception as exc:
            processing_time = time.time() - start_time
            logger.exception("hierarchical orchestration failed")
            context.final_output = f"处理出错：{str(exc)}"
            context.risk_level = RiskLevel.HIGH
            context.requires_human_review = True
            context.can_export = False
            context.review_status = "pending_review"
            self.store.update_task(
                task.task_id,
                status="failed",
                intent=context.intent.value if context.intent else "unknown",
                risk_level=RiskLevel.HIGH.value,
                final_output=context.final_output,
                error=str(exc),
            )
            return ProcessResult(
                success=False,
                task_id=context.request_id,
                trace_id=context.trace_id,
                output=context.final_output,
                intent=context.intent or IntentType.UNKNOWN,
                risk_level=RiskLevel.HIGH,
                confidence=context.confidence,
                tools_used=context.tools_used,
                requires_human_review=True,
                can_export=False,
                profile_record_ids=context.profile_record_ids,
                profile_strategy=context.profile_strategy,
                review_status="pending_review",
                error=str(exc),
                processing_time=processing_time,
            )
        finally:
            await self.legacy._log_audit(context)

    async def _recognize_intent(self, user_input: str, context: ProcessingContext) -> None:
        step = self.store.add_step(
            task_id=context.request_id,
            name="intent.recognize",
            role="root_orchestrator",
            sequence=1,
            input_data={"user_input": user_input[:500]},
        )
        try:
            intent_result = await self.legacy.intent_recognizer.recognize(user_input)
            context.intent = intent_result.intent
            context.confidence = intent_result.confidence
            self.store.finish_step(
                step.step_id,
                output_data={
                    "intent": context.intent.value,
                    "confidence": context.confidence,
                    "keywords": intent_result.keywords,
                },
            )
        except Exception as exc:
            self.store.finish_step(step.step_id, status="failed", error=str(exc))
            raise

    def _apply_profile(self, user_input: str, context: ProcessingContext) -> None:
        step = self.store.add_step(
            task_id=context.request_id,
            name="profile.match_strategy",
            role="root_orchestrator",
            sequence=2,
            input_data={"intent": context.intent.value if context.intent else "unknown"},
        )
        before_tools = len(context.tools_used)
        try:
            self.legacy._apply_profile_strategy(user_input, context)
            self._record_new_tools(context, step.step_id, before_tools)
            self.store.finish_step(
                step.step_id,
                output_data={
                    "profile_record_ids": context.profile_record_ids,
                    "profile_strategy": context.profile_strategy,
                },
            )
        except Exception as exc:
            self.store.finish_step(step.step_id, status="failed", error=str(exc))
            raise

    async def _execute_workflow(self, user_input: str, context: ProcessingContext) -> str:
        outputs: List[str] = []
        specs = self.planner.plan(context.intent or IntentType.UNKNOWN)
        for index, spec in enumerate(specs, start=3):
            step = self.store.add_step(
                task_id=context.request_id,
                name=spec.name,
                role=spec.role,
                sequence=index,
                input_data={"intent": context.intent.value if context.intent else "unknown"},
            )
            before_tools = len(context.tools_used)
            try:
                result = await self.supervisor.execute(
                    role=spec.role,
                    step_name=spec.name,
                    user_input=user_input,
                    context=context,
                )
                self._record_new_tools(context, step.step_id, before_tools)
                self.store.finish_step(
                    step.step_id,
                    output_data=result.model_dump() if hasattr(result, "model_dump") else {},
                )
                if result.content and spec.role != "review_supervisor":
                    outputs.append(result.content)
            except Exception as exc:
                self.store.finish_step(step.step_id, status="failed", error=str(exc))
                raise
        return "\n\n".join(output for output in outputs if output).strip()

    async def _label_risk(self, context: ProcessingContext, output: str) -> None:
        step = self.store.add_step(
            task_id=context.request_id,
            name="risk.label",
            role="review_supervisor",
            sequence=100,
            input_data={"intent": context.intent.value if context.intent else "unknown"},
        )
        try:
            risk_result = await self.legacy.risk_labeler.label_detailed(
                intent=context.intent,
                content=output,
            )
            context.risk_level = risk_result.level
            context.requires_human_review = risk_result.requires_confirmation
            context.can_export = risk_result.can_export
            context.review_status = (
                "pending_review" if risk_result.requires_confirmation else "not_required"
            )
            self.store.finish_step(
                step.step_id,
                output_data={
                    "risk_level": context.risk_level.value,
                    "requires_human_review": context.requires_human_review,
                    "can_export": context.can_export,
                },
            )
        except Exception as exc:
            self.store.finish_step(step.step_id, status="failed", error=str(exc))
            raise

    def _record_new_tools(
        self,
        context: ProcessingContext,
        step_id: str,
        before_index: int,
    ) -> None:
        for tool_name in context.tools_used[before_index:]:
            provider = tool_name.split(".", 1)[0] if "." in tool_name else ""
            self.store.add_tool_call(
                task_id=context.request_id,
                step_id=step_id,
                provider=provider,
                tool_name=tool_name,
                status="ok",
                input_summary=context.user_input[:120],
                output_summary="",
            )
