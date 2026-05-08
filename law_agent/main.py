"""
律师智能体主入口

提供：
1. 应用初始化
2. API服务
3. 命令行工具
"""

import asyncio
import inspect
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from law_agent import LawOrchestrator
from law_agent.tools import (
    ToolRegistry,
    RAGClient,
    RegulationSearchTool,
    CaseSearchTool,
    CitationVerifyTool,
    DocumentTool,
)
from law_agent.sub_agents import ResearchAgent, DocumentAgent
from law_agent.intent import IntentRecognizer
from law_agent.risk import RiskLabeler
from law_agent.audit import AuditLog, AuditLogger
from law_agent.client_profiles import ClientProfileStore
from law_agent.llm import create_llm_client
from law_agent.review import ReviewTaskStore
from config.settings import get_config


class ExternalActionError(Exception):
    """对外发送/导出门禁错误。"""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class LawAgentApp:
    """
    律师智能体应用
    
    负责：
    1. 初始化各组件
    2. 提供API接口
    3. 管理生命周期
    """
    
    def __init__(self):
        self.config = get_config()
        self.orchestrator: LawOrchestrator = None
        self.audit_logger = AuditLogger(self.config.database.audit_db_path)
        self.profile_store = ClientProfileStore(self.config.database.client_profile_db_path)
        self.review_store = ReviewTaskStore(self.config.database.task_db_path)
        self.llm_client = None
        self._initialized = False
    
    async def initialize(self):
        """初始化应用"""
        if self._initialized:
            return
        
        print("🚀 初始化律师智能体...")
        
        # 初始化RAG客户端
        rag_client = RAGClient(
            api_endpoint=self.config.rag.api_endpoint,
            api_key=self.config.rag.api_key,
            timeout=self.config.rag.timeout,
        )
        
        # 检查RAG连接
        if await rag_client.health_check():
            print("✅ RAG库连接成功")
        else:
            print("⚠️ RAG库连接失败，继续启动...")

        self.llm_client = create_llm_client(self.config.llm)
        if self.llm_client:
            print(f"✅ LLM客户端已启用：{self.config.llm.provider}/{self.config.llm.model}")
        else:
            print("⚠️ 未配置LLM API Key，继续使用规则和模板逻辑")
        
        # 初始化工具
        tool_registry = ToolRegistry()
        
        regulation_tool = RegulationSearchTool(rag_client)
        case_tool = CaseSearchTool(rag_client)
        citation_tool = CitationVerifyTool(rag_client)
        document_tool = DocumentTool()
        
        tool_registry.register_tool(regulation_tool)
        tool_registry.register_tool(case_tool)
        tool_registry.register_tool(citation_tool)
        tool_registry.register_tool(document_tool)
        
        # 初始化子Agent
        research_agent = ResearchAgent(rag_client, self.llm_client)
        document_agent = DocumentAgent(self.llm_client)
        
        # 初始化核心组件
        intent_recognizer = IntentRecognizer(self.llm_client)
        risk_labeler = RiskLabeler(self.llm_client)
        # 初始化主编排器
        self.orchestrator = LawOrchestrator(
            llm_client=self.llm_client,
            tool_registry=tool_registry,
            intent_recognizer=intent_recognizer,
            risk_labeler=risk_labeler,
            audit_logger=self.audit_logger,
            research_agent=research_agent,
            document_agent=document_agent,
            client_profile_store=self.profile_store,
        )
        
        self._initialized = True
        print("✅ 律师智能体初始化完成")
    
    async def process(self, user_input: str, session_id: str = "", user_id: str = "") -> dict:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入
            session_id: 会话ID
            user_id: 用户ID
            
        Returns:
            dict: 处理结果
        """
        if not self._initialized:
            await self.initialize()
        
        result = await self.orchestrator.process(
            user_input=user_input,
            session_id=session_id,
            user_id=user_id,
        )

        review_task = None
        if result.requires_human_review and getattr(self, "review_store", None):
            task_title = await self._generate_review_task_title(
                user_input=user_input,
                intent=result.intent.value,
                risk_level=result.risk_level.value,
            )
            review_task = self.review_store.create_pending(
                trace_id=result.trace_id,
                task_id=result.task_id,
                session_id=session_id,
                user_id=user_id,
                intent=result.intent.value,
                risk_level=result.risk_level.value,
                original_output=result.output,
                user_input=user_input,
                task_title=task_title,
            )
        
        llm_runtime = self._build_llm_runtime(result.tools_used)

        return {
            "success": result.success,
            "task_id": result.task_id,
            "trace_id": result.trace_id,
            "output": result.output,
            "intent": result.intent.value,
            "risk_level": result.risk_level.value,
            "confidence": result.confidence,
            "tools_used": result.tools_used,
            "requires_human_review": result.requires_human_review,
            "can_export": result.can_export,
            "profile_record_ids": result.profile_record_ids,
            "profile_strategy": result.profile_strategy,
            "review_status": result.review_status,
            "review_task": review_task.to_dict() if review_task else None,
            "llm_enabled": llm_runtime["enabled"],
            "llm_status": llm_runtime["status"],
            "llm_tools_used": llm_runtime["tools_used"],
            "llm_model": llm_runtime["model"],
            "llm_fallback_models": llm_runtime["fallback_models"],
            "processing_time": result.processing_time,
            "error": result.error,
        }

    def _build_llm_runtime(self, tools_used: list[str]) -> dict:
        """生成给 API/工作台展示的 LLM 运行状态，不暴露密钥。"""
        llm_tools = [tool for tool in tools_used if tool.startswith("llm.")]
        enabled = bool(getattr(self, "llm_client", None)) or bool(llm_tools)
        failed = [tool for tool in llm_tools if "failed" in tool]

        if not enabled:
            status = "disabled"
        elif llm_tools and failed and len(failed) == len(llm_tools):
            status = "failed"
        elif failed:
            status = "called_with_fallback"
        elif llm_tools:
            status = "called"
        else:
            status = "not_called"

        return {
            "enabled": enabled,
            "status": status,
            "tools_used": llm_tools,
            "model": self.config.llm.model if enabled else "",
            "fallback_models": self.config.llm.fallback_models if enabled else [],
        }

    async def _generate_review_task_title(
        self,
        user_input: str,
        intent: str,
        risk_level: str,
    ) -> str:
        """生成审阅任务列表里展示的一句话标题。"""
        fallback = self._fallback_review_task_title(user_input, intent)
        llm_client = getattr(self, "llm_client", None)
        if not llm_client:
            return fallback

        prompt = f"""
请为律师工作台的人工审阅任务生成一句中文概要标题。

用户输入：
{user_input}

意图：{intent}
风险等级：{risk_level}

要求：
1. 只输出一句话标题，不要解释。
2. 不超过 24 个中文字符。
3. 用自然语言概括事项，不要输出 trace_id、任务ID 或字段名。
4. 避免“关于……的问题”这种空泛标题。
"""
        try:
            title = await llm_client.call(
                prompt,
                system_prompt="你是律师工作台任务标题生成器，只输出短标题。",
                temperature=0.2,
                max_tokens=80,
            )
        except Exception:
            return fallback

        title = title.strip().strip("`\"'“”‘’")
        title = " ".join(title.split())
        if not title:
            return fallback
        return title[:32]

    def _fallback_review_task_title(self, user_input: str, intent: str) -> str:
        """LLM 不可用时的简短标题兜底。"""
        text = " ".join((user_input or "").split())
        if text:
            return text[:28]
        intent_labels = {
            "regulation_query": "法规查询待审阅",
            "case_search": "类案检索待审阅",
            "document_draft": "文书草稿待审阅",
            "contract_review": "合同审查待审阅",
            "general": "通用答复待审阅",
        }
        return intent_labels.get(intent, "待审阅任务")

    def import_profiles(self, json_file_path: str) -> dict:
        """导入客户画像 JSON。"""
        summary = self.profile_store.ingest_json_file(json_file_path)
        return {
            "import_id": summary.import_id,
            "source_file": summary.source_file,
            "records_seen": summary.records_seen,
            "records_upserted": summary.records_upserted,
            "records_skipped": summary.records_skipped,
            "db_path": self.profile_store.db_path,
        }

    def list_profiles(
        self,
        matter_type: str = None,
        stage: str = None,
        client_goal: str = None,
        first_judgment: str = None,
        ingestion_level: str = None,
        limit: int = 20,
    ) -> list[dict]:
        """查询可作为编排驱动的画像记录。"""
        return self.profile_store.list_driver_profiles(
            matter_type=matter_type,
            stage=stage,
            client_goal=client_goal,
            first_judgment=first_judgment,
            ingestion_level=ingestion_level,
            limit=limit,
        )

    def get_profile(self, record_id: str) -> dict | None:
        """按 record_id 查询画像记录。"""
        return self.profile_store.get_record(record_id)

    async def query_audit(
        self,
        user_id: str = None,
        intent: str = None,
        risk_level: str = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询审计日志。"""
        logs = await self.audit_logger.query(
            user_id=user_id,
            intent=intent,
            risk_level=risk_level,
            limit=limit,
        )
        return [_serialize_audit_log(log) for log in logs]

    async def query_external_actions(
        self,
        trace_id: str = None,
        user_id: str = None,
        action_type: str = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询对外发送/导出审计明细。"""
        return await self.audit_logger.query_external_actions(
            trace_id=trace_id,
            user_id=user_id,
            action_type=action_type,
            limit=limit,
        )

    async def list_review_tasks(
        self,
        review_status: str = None,
        user_id: str = None,
        risk_level: str = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询人工审阅任务。"""
        tasks = self.review_store.list_tasks(
            review_status=review_status,
            user_id=user_id,
            risk_level=risk_level,
            limit=limit,
        )
        items = []
        for task in tasks:
            item = task.to_dict()
            audit_log = await self.audit_logger.get_by_trace_id(task.trace_id)
            if audit_log:
                tools_used = audit_log.tools_used.split(",") if audit_log.tools_used else []
                llm_runtime = self._build_llm_runtime(tools_used)
                user_input = item.get("user_input") or audit_log.input_summary
                task_title = item.get("task_title")
                if not task_title:
                    task_title = await self._generate_review_task_title(
                        user_input=user_input,
                        intent=task.intent,
                        risk_level=task.risk_level,
                    )
                    self.review_store.update_task_metadata(
                        trace_id=task.trace_id,
                        user_input=user_input,
                        task_title=task_title,
                    )
                item.update(
                    {
                        "user_input": user_input,
                        "task_title": task_title,
                        "tools_used": tools_used,
                        "profile_record_ids": _extract_profile_record_ids(audit_log.tools_used),
                        "llm_enabled": llm_runtime["enabled"],
                        "llm_status": llm_runtime["status"],
                        "llm_tools_used": llm_runtime["tools_used"],
                        "llm_model": llm_runtime["model"],
                        "llm_fallback_models": llm_runtime["fallback_models"],
                    }
                )
            else:
                item.setdefault("tools_used", [])
                item.setdefault("profile_record_ids", [])
            items.append(item)
        return items

    async def confirm_review(
        self,
        trace_id: str,
        reviewer_id: str,
        reviewed_output: str = None,
    ) -> dict | None:
        """确认审阅任务，并同步审计确认标记。"""
        task = self.review_store.confirm(
            trace_id=trace_id,
            reviewer_id=reviewer_id,
            reviewed_output=reviewed_output,
        )
        if task is None:
            return None
        await self.audit_logger.set_confirmation(trace_id, True)
        return task.to_dict()

    async def reject_review(
        self,
        trace_id: str,
        reviewer_id: str,
        rejection_reason: str,
    ) -> dict | None:
        """驳回审阅任务，并同步审计确认标记。"""
        task = self.review_store.reject(
            trace_id=trace_id,
            reviewer_id=reviewer_id,
            rejection_reason=rejection_reason,
        )
        if task is None:
            return None
        await self.audit_logger.set_confirmation(trace_id, False)
        return task.to_dict()

    async def export_output(
        self,
        trace_id: str,
        actor_id: str,
        export_format: str = "markdown",
        destination: str = "",
    ) -> dict:
        """导出已经通过风控门禁的输出。"""
        return await self._record_external_action(
            trace_id=trace_id,
            actor_id=actor_id,
            action_type="export",
            export_format=export_format,
            destination=destination,
        )

    async def send_output(
        self,
        trace_id: str,
        actor_id: str,
        destination: str,
    ) -> dict:
        """记录人工触发的对外发送动作。"""
        return await self._record_external_action(
            trace_id=trace_id,
            actor_id=actor_id,
            action_type="send",
            export_format="",
            destination=destination,
        )

    async def _record_external_action(
        self,
        trace_id: str,
        actor_id: str,
        action_type: str,
        export_format: str = "markdown",
        destination: str = "",
    ) -> dict:
        audit_log = await self.audit_logger.get_by_trace_id(trace_id)
        if audit_log is None:
            raise ExternalActionError("audit log not found", status_code=404)

        review_task = self.review_store.get(trace_id) if self.review_store else None
        risk_requires_review = audit_log.risk_level in {"medium", "high"}
        review_status = "not_required"
        reviewer_id = None
        reviewed_at = None
        original_output = audit_log.output_summary or ""
        final_output = audit_log.output_summary or ""
        confirmed = False

        if review_task is not None:
            review_status = review_task.review_status
            reviewer_id = review_task.reviewer_id
            reviewed_at = review_task.reviewed_at
            original_output = review_task.original_output
            final_output = review_task.reviewed_output or review_task.original_output
            confirmed = review_task.review_status == "confirmed"

        if risk_requires_review:
            if review_task is None:
                raise ExternalActionError(
                    "medium/high risk output requires a review task before external action",
                    status_code=409,
                )
            if review_task.review_status == "pending_review":
                raise ExternalActionError(
                    "content is still pending human review",
                    status_code=409,
                )
            if review_task.review_status == "rejected":
                raise ExternalActionError(
                    "rejected content cannot be exported or sent",
                    status_code=403,
                )
            if review_task.review_status != "confirmed":
                raise ExternalActionError(
                    "content must be confirmed before external action",
                    status_code=409,
                )

        profile_record_ids = _extract_profile_record_ids(audit_log.tools_used)
        action_log = await self.audit_logger.log_external_action(
            task_id=audit_log.task_id,
            trace_id=audit_log.trace_id,
            user_id=audit_log.user_id,
            actor_id=actor_id,
            action_type=action_type,
            export_format=export_format,
            destination=destination,
            risk_level=audit_log.risk_level,
            review_status=review_status,
            confirmed=confirmed,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
            original_output=original_output,
            final_output=final_output,
            profile_record_ids=profile_record_ids,
        )

        return {
            "allowed": True,
            "trace_id": audit_log.trace_id,
            "task_id": audit_log.task_id,
            "action_type": action_type,
            "risk_level": audit_log.risk_level,
            "review_status": review_status,
            "requires_human_review": risk_requires_review,
            "can_export": True,
            "actor_id": actor_id,
            "reviewer_id": reviewer_id,
            "reviewed_at": reviewed_at,
            "profile_record_ids": profile_record_ids,
            "content": final_output,
            "audit": action_log,
        }
    
    async def shutdown(self):
        """关闭应用"""
        print("👋 关闭律师智能体...")


# ===== API服务 =====

def _serialize_audit_log(log: AuditLog) -> dict:
    """将审计日志转成 API 友好的字典。"""
    data = {
        "task_id": log.task_id,
        "session_id": log.session_id,
        "trace_id": log.trace_id,
        "user_id": log.user_id,
        "intent": log.intent,
        "input_summary": log.input_summary,
        "output_summary": log.output_summary,
        "tools_used": log.tools_used.split(",") if log.tools_used else [],
        "risk_level": log.risk_level,
        "confirmed": log.confirmed,
        "exported": log.exported,
        "log_level": log.log_level,
        "error_message": log.error_message,
    }
    timestamp = log.timestamp
    data["timestamp"] = timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp
    return data


def _extract_profile_record_ids(tools_used: str) -> list[str]:
    """从审计工具列表里恢复命中过的画像规则 ID。"""
    profile_ids = []
    for item in (tools_used or "").split(","):
        if item.startswith("client_profile:"):
            profile_ids.append(item.removeprefix("client_profile:"))
    return profile_ids


def create_api_app(law_app: LawAgentApp = None):
    """创建 FastAPI 应用，便于服务启动和测试复用。"""
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel, Field

    app = FastAPI(title="律师智能体 API")
    law_app = law_app or LawAgentApp()

    class ProcessRequest(BaseModel):
        user_input: str
        session_id: str = ""
        user_id: str = ""

    class ProfileImportRequest(BaseModel):
        json_file_path: str = Field(..., description="服务器本地画像 JSON 文件路径")

    class ReviewConfirmRequest(BaseModel):
        trace_id: str
        reviewer_id: str
        reviewed_output: str | None = None

    class ReviewRejectRequest(BaseModel):
        trace_id: str
        reviewer_id: str
        rejection_reason: str

    class ExternalActionRequest(BaseModel):
        trace_id: str
        actor_id: str = Field(..., description="执行导出或发送动作的人员 ID")
        export_format: str = "markdown"
        destination: str = ""

    @app.on_event("startup")
    async def startup():
        await law_app.initialize()

    @app.on_event("shutdown")
    async def shutdown():
        await law_app.shutdown()

    @app.post("/api/v1/process")
    async def process_request(request: ProcessRequest):
        """处理用户请求"""
        result = await law_app.process(
            user_input=request.user_input,
            session_id=request.session_id,
            user_id=request.user_id,
        )
        return result

    @app.get("/workbench", response_class=HTMLResponse)
    async def workbench():
        """Web 工作台 MVP。"""
        workbench_path = Path(__file__).parent / "static" / "workbench.html"
        return HTMLResponse(workbench_path.read_text(encoding="utf-8"))

    @app.post("/api/v1/profiles/import")
    async def import_profiles(request: ProfileImportRequest):
        """导入客户画像 JSON。"""
        try:
            return law_app.import_profiles(request.json_file_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/profiles")
    async def list_profiles(
        matter_type: str = None,
        stage: str = None,
        client_goal: str = None,
        first_judgment: str = None,
        ingestion_level: str = None,
        limit: int = Query(default=20, ge=1, le=100),
    ):
        """查询客户画像。"""
        return {
            "items": law_app.list_profiles(
                matter_type=matter_type,
                stage=stage,
                client_goal=client_goal,
                first_judgment=first_judgment,
                ingestion_level=ingestion_level,
                limit=limit,
            )
        }

    @app.get("/api/v1/profiles/{record_id}")
    async def get_profile(record_id: str):
        """按 record_id 查询客户画像。"""
        record = law_app.get_profile(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="profile not found")
        return record

    @app.get("/api/v1/audit")
    async def query_audit(
        user_id: str = None,
        intent: str = None,
        risk_level: str = None,
        limit: int = Query(default=100, ge=1, le=500),
    ):
        """查询审计日志。"""
        return {
            "items": await law_app.query_audit(
                user_id=user_id,
                intent=intent,
                risk_level=risk_level,
                limit=limit,
            )
        }

    @app.get("/api/v1/audit/external-actions")
    async def query_external_actions(
        trace_id: str = None,
        user_id: str = None,
        action_type: str = None,
        limit: int = Query(default=100, ge=1, le=500),
    ):
        """查询对外发送/导出审计明细。"""
        return {
            "items": await law_app.query_external_actions(
                trace_id=trace_id,
                user_id=user_id,
                action_type=action_type,
                limit=limit,
            )
        }

    @app.get("/api/v1/review/tasks")
    async def list_review_tasks(
        review_status: str = None,
        user_id: str = None,
        risk_level: str = None,
        limit: int = Query(default=100, ge=1, le=500),
    ):
        """查询人工审阅任务。"""
        items = law_app.list_review_tasks(
            review_status=review_status,
            user_id=user_id,
            risk_level=risk_level,
            limit=limit,
        )
        if inspect.isawaitable(items):
            items = await items
        return {
            "items": items
        }

    @app.post("/api/v1/review/confirm")
    async def confirm_review(request: ReviewConfirmRequest):
        """确认人工审阅任务。"""
        task = await law_app.confirm_review(
            trace_id=request.trace_id,
            reviewer_id=request.reviewer_id,
            reviewed_output=request.reviewed_output,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="review task not found")
        return task

    @app.post("/api/v1/review/reject")
    async def reject_review(request: ReviewRejectRequest):
        """驳回人工审阅任务。"""
        task = await law_app.reject_review(
            trace_id=request.trace_id,
            reviewer_id=request.reviewer_id,
            rejection_reason=request.rejection_reason,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="review task not found")
        return task

    @app.post("/api/v1/export")
    async def export_output(request: ExternalActionRequest):
        """导出输出。中高风险内容必须先人工确认。"""
        try:
            return await law_app.export_output(
                trace_id=request.trace_id,
                actor_id=request.actor_id,
                export_format=request.export_format,
                destination=request.destination,
            )
        except ExternalActionError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @app.post("/api/v1/send")
    async def send_output(request: ExternalActionRequest):
        """记录人工触发的对外发送动作。"""
        try:
            return await law_app.send_output(
                trace_id=request.trace_id,
                actor_id=request.actor_id,
                destination=request.destination,
            )
        except ExternalActionError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @app.get("/api/v1/health")
    async def health_check():
        """健康检查"""
        if not law_app._initialized:
            await law_app.initialize()
        llm_runtime = law_app._build_llm_runtime([])
        return {
            "status": "ok",
            "llm_enabled": llm_runtime["enabled"],
            "llm_status": llm_runtime["status"],
            "llm_model": llm_runtime["model"],
            "llm_fallback_models": llm_runtime["fallback_models"],
        }

    @app.get("/api/v1/stats")
    async def get_stats():
        """获取统计信息"""
        return await law_app.audit_logger.get_statistics()

    return app


def run_api_server():
    """运行API服务"""
    import uvicorn

    app = create_api_app()
    config = get_config()
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )


# ===== CLI工具 =====

async def run_cli():
    """运行命令行交互"""
    law_app = LawAgentApp()
    await law_app.initialize()
    
    print("\n" + "="*50)
    print("欢迎使用律师智能体 CLI")
    print("="*50)
    print("输入您的法律问题，按回车发送")
    print("输入 'quit' 或 'exit' 退出")
    print("="*50 + "\n")
    
    while True:
        try:
            user_input = input("👤 您: ").strip()
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 再见！")
                break
            
            if not user_input:
                continue
            
            result = await law_app.process(user_input)
            
            print(f"\n🤖 律师智能体:")
            print("-"*40)
            print(result["output"])
            print("-"*40)
            
            if result.get("error"):
                print(f"❌ 错误: {result['error']}")
            
            print(f"\n📊 trace_id: {result['trace_id']}")
            print(f"📊 风险等级: {result['risk_level']}")
            print(f"📊 处理时间: {result['processing_time']:.2f}s")
            print()
            
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 出错: {e}")


# ===== 入口点 =====

def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="律师智能体")
    parser.add_argument(
        "mode",
        choices=["api", "cli", "test"],
        default="cli",
        help="运行模式: api=API服务, cli=命令行交互, test=测试模式"
    )
    
    args = parser.parse_args()
    
    if args.mode == "api":
        run_api_server()
    elif args.mode == "cli":
        asyncio.run(run_cli())
    elif args.mode == "test":
        asyncio.run(run_test())


async def run_test():
    """运行测试"""
    law_app = LawAgentApp()
    await law_app.initialize()
    test_cases = [
        {
            "input": "公司拖欠工资三个月，员工是否可以立即解除劳动合同？",
            "expected_intent": "regulation_query",
        },
        {
            "input": "帮我找建设工程领域关于实际施工人主张工程价款的案例",
            "expected_intent": "case_search",
        },
        {
            "input": "生成一份民事起诉状",
            "expected_intent": "document_draft",
        },
    ]
    # dfhbdfgbgdfgfd
    print("🧪 开始测试...\n")
    
    for i, test in enumerate(test_cases, 1):
        print(f"测试 {i}: {test['input']}")
        result = await law_app.process(test["input"])
        print(f"  意图: {result['intent']} (期望: {test['expected_intent']})")
        print(f"  风险: {result['risk_level']}")
        print(f"  成功: {result['success']}")
        print()
    
    print("✅ 测试完成")


if __name__ == "__main__":
    main()
