"""
主编排器 (Orchestrator)
律师智能体的核心调度中心

职责：
1. 接收用户输入
2. 意图识别
3. 路由到对应的处理函数
4. 聚合结果
5. 添加风险标签
6. 记录审计日志

设计原则：
- 简单直接，代码即文档
- if/elif路由，足够法律场景
- 完全可追溯
"""

import asyncio
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .intent import IntentRecognizer, IntentType
from .risk import RiskLabeler, RiskLevel
from .audit import AuditLogger, AuditLog
from .client_profiles import ClientProfileStore
from .tools import ToolRegistry
from .sub_agents import ResearchAgent, DocumentAgent


@dataclass
class ProcessingContext:
    """处理上下文 - 贯穿整个请求生命周期"""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    user_id: str = ""
    user_input: str = ""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.now)
    
    # 意图识别结果
    intent: Optional[IntentType] = None
    confidence: float = 0.0
    
    # 工具调用记录
    tools_used: List[str] = field(default_factory=list)
    profile_record_ids: List[str] = field(default_factory=list)
    profile_strategy: Dict[str, Any] = field(default_factory=dict)
    
    # 中间结果
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    
    # 最终输出
    final_output: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    requires_human_review: bool = False
    can_export: bool = True
    review_status: str = "not_required"
    
    # 用户确认
    confirmed: bool = False
    exported: bool = False


@dataclass 
class ProcessResult:
    """处理结果"""
    success: bool
    task_id: str
    trace_id: str
    output: str
    intent: IntentType
    risk_level: RiskLevel
    confidence: float
    tools_used: List[str]
    requires_human_review: bool = False
    can_export: bool = True
    profile_record_ids: List[str] = field(default_factory=list)
    profile_strategy: Dict[str, Any] = field(default_factory=dict)
    review_status: str = "not_required"
    error: Optional[str] = None
    processing_time: float = 0.0


class LawOrchestrator:
    """
    律师智能体主编排器
    
    工作流程：
    1. 接收用户输入
    2. 创建处理上下文
    3. 意图识别
    4. 根据意图路由到对应的子Agent
    5. 子Agent调用工具完成处理
    6. 添加风险标签
    7. 记录审计日志
    8. 返回标准化响应
    """
    
    def __init__(
        self,
        llm_client: Any,  # LLM客户端接口
        tool_registry: ToolRegistry,
        intent_recognizer: IntentRecognizer,
        risk_labeler: RiskLabeler,
        audit_logger: AuditLogger,
        research_agent: ResearchAgent,
        document_agent: DocumentAgent,
        client_profile_store: Optional[ClientProfileStore] = None,
    ):
        self.llm = llm_client
        self.tools = tool_registry
        self.intent_recognizer = intent_recognizer
        self.risk_labeler = risk_labeler
        self.audit_logger = audit_logger
        self.research = research_agent
        self.document = document_agent
        self.client_profiles = client_profile_store
        
        # 加载Prompt模板
        self._load_prompts()
    
    def _load_prompts(self):
        """加载Prompt模板"""
        # TODO: 从配置文件加载
        self.unknown_intent_response = "抱歉，我无法理解您的问题。请尝试：\n- 法规查询：'公司拖欠工资三个月，员工是否可以立即解除劳动合同？'\n- 类案检索：'帮我找建设工程领域关于实际施工人主张工程价款的案例'\n- 文书生成：'生成一份民事起诉状'"
    
    async def process(
        self,
        user_input: str,
        session_id: str = "",
        user_id: str = "",
    ) -> ProcessResult:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入的自然语言
            session_id: 会话ID
            user_id: 用户ID
            
        Returns:
            ProcessResult: 处理结果
        """
        # 创建处理上下文
        context = ProcessingContext(
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
        )
        
        start_time = time.time()
        
        try:
            # Step 1: 意图识别
            intent_result = await self.intent_recognizer.recognize(user_input)
            context.intent = intent_result.intent
            context.confidence = intent_result.confidence
            self._apply_profile_strategy(user_input, context)
            
            # 置信度低于阈值时，优先交给通用 LLM 助手；未配置 LLM 才返回菜单提示。
            if intent_result.confidence < 0.5:
                if self.llm:
                    context.intent = IntentType.GENERAL
                    output = await self._handle_general(user_input, context)
                else:
                    output = self.unknown_intent_response
            else:
                # Step 2: 根据意图路由处理
                output = await self._route_intent(user_input, context)
                output = self._append_profile_strategy(output, context)
            
            context.final_output = output
            
            # Step 3: 风险标签
            risk_result = await self.risk_labeler.label_detailed(
                intent=context.intent,
                content=output,
            )
            context.risk_level = risk_result.level
            context.requires_human_review = risk_result.requires_confirmation
            context.can_export = risk_result.can_export
            context.review_status = (
                "pending_review" if risk_result.requires_confirmation else "not_required"
            )
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
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
            
        except Exception as e:
            processing_time = time.time() - start_time
            return ProcessResult(
                success=False,
                task_id=context.request_id,
                trace_id=context.trace_id,
                output=f"处理出错：{str(e)}",
                intent=IntentType.UNKNOWN,
                risk_level=RiskLevel.HIGH,
                confidence=0.0,
                tools_used=context.tools_used,
                requires_human_review=True,
                can_export=False,
                profile_record_ids=context.profile_record_ids,
                profile_strategy=context.profile_strategy,
                review_status="pending_review",
                error=str(e),
                processing_time=processing_time,
            )
        
        finally:
            # Step 4: 记录审计日志
            await self._log_audit(context)
    
    async def _route_intent(
        self,
        user_input: str,
        context: ProcessingContext,
    ) -> str:
        """
        根据意图路由到对应的处理函数
        
        简单的if/elif路由，对于固定流程的法律场景足够高效
        """
        
        if context.intent == IntentType.REGULATION_QUERY:
            return await self._handle_regulation_query(user_input, context)
            
        elif context.intent == IntentType.CASE_SEARCH:
            return await self._handle_case_search(user_input, context)
            
        elif context.intent == IntentType.DOCUMENT_DRAFT:
            return await self._handle_document_draft(user_input, context)
            
        elif context.intent == IntentType.CONTRACT_REVIEW:
            return await self._handle_contract_review(user_input, context)
            
        elif context.intent == IntentType.GENERAL:
            return await self._handle_general(user_input, context)
            
        else:
            return self.unknown_intent_response

    def _apply_profile_strategy(self, user_input: str, context: ProcessingContext) -> None:
        """匹配客户画像规则，并把可用策略写入上下文。"""
        if not self.client_profiles:
            return

        filters = self._extract_profile_filters(user_input, context.intent)
        if not filters.get("matter_type"):
            return

        profiles = self.client_profiles.list_driver_profiles(**filters, limit=3)
        if not profiles:
            fallback_filters = {
                "matter_type": filters.get("matter_type"),
                "stage": filters.get("stage"),
                "ingestion_level": filters.get("ingestion_level"),
            }
            profiles = self.client_profiles.list_driver_profiles(**fallback_filters, limit=3)

        if not profiles:
            return

        context.profile_record_ids = [
            profile["record_id"] for profile in profiles if profile.get("record_id")
        ]
        primary = profiles[0]
        context.profile_strategy = {
            "matched_filters": {key: value for key, value in filters.items() if value},
            "record_ids": context.profile_record_ids,
            "strategy_choice": primary.get("strategy_choice"),
            "risk_communication": primary.get("risk_communication"),
            "handling_temperature": primary.get("handling_temperature"),
            "reusable_rule": primary.get("reusable_rule"),
            "external_document_suitability": self._assess_external_document_suitability(
                context.intent,
                primary,
            ),
        }
        context.tools_used.append("client_profiles.match_driver_profiles")

    def _extract_profile_filters(
        self,
        user_input: str,
        intent: Optional[IntentType],
    ) -> Dict[str, Optional[str]]:
        """用轻量规则抽取画像匹配字段。"""
        return {
            "matter_type": self._guess_matter_type(user_input, intent),
            "stage": self._guess_stage(user_input, intent),
            "client_goal": self._guess_client_goal(user_input),
            "first_judgment": self._guess_first_judgment(user_input, intent),
            "ingestion_level": "A核心画像",
        }

    def _guess_matter_type(
        self,
        user_input: str,
        intent: Optional[IntentType],
    ) -> Optional[str]:
        text = user_input.lower()
        if any(keyword in user_input for keyword in ["合同", "借款", "买卖", "租赁"]):
            return "民事合同"
        if any(keyword in user_input for keyword in ["建设工程", "工程价款", "实际施工人"]):
            return "建设工程"
        if any(keyword in user_input for keyword in ["工资", "劳动", "工伤"]):
            return "劳动争议"
        if any(keyword in user_input for keyword in ["离婚", "抚养", "继承"]):
            return "婚姻家事"
        if intent == IntentType.DOCUMENT_DRAFT and "起诉状" in user_input:
            return "民事合同"
        if "contract" in text:
            return "民事合同"
        return None

    def _guess_stage(
        self,
        user_input: str,
        intent: Optional[IntentType],
    ) -> Optional[str]:
        if any(keyword in user_input for keyword in ["起诉", "诉讼", "上诉", "答辩"]):
            return "诉讼"
        if any(keyword in user_input for keyword in ["咨询", "能否", "是否", "怎么办"]):
            return "咨询"
        if intent in [IntentType.REGULATION_QUERY, IntentType.GENERAL]:
            return "咨询"
        return None

    def _guess_client_goal(self, user_input: str) -> Optional[str]:
        """从用户输入中推断客户目标。"""
        if any(keyword in user_input for keyword in ["止损", "减少损失", "降低损失"]):
            return "止损"
        if any(keyword in user_input for keyword in ["拿回", "追回", "回款", "要钱", "工程价款"]):
            return "回款"
        if any(keyword in user_input for keyword in ["解除", "终止", "退出"]):
            return "解除关系"
        if any(keyword in user_input for keyword in ["赔偿", "补偿", "违约金"]):
            return "争取赔偿"
        if any(keyword in user_input for keyword in ["审查", "风险", "避坑", "合规"]):
            return "控制风险"
        if any(keyword in user_input for keyword in ["起诉", "上诉", "申诉"]):
            return "推进诉讼"
        return None

    def _guess_first_judgment(
        self,
        user_input: str,
        intent: Optional[IntentType],
    ) -> Optional[str]:
        """从输入和意图推断初步判断。"""
        if any(keyword in user_input for keyword in ["证据不足", "没有证据", "缺少证据"]):
            return "需补证据"
        if any(keyword in user_input for keyword in ["期限", "时效", "截止", "上诉期"]):
            return "高风险"
        if intent == IntentType.DOCUMENT_DRAFT:
            return "需人工审阅"
        if intent == IntentType.CONTRACT_REVIEW:
            return "需审查"
        if any(keyword in user_input for keyword in ["能否", "是否", "可以吗", "怎么办"]):
            return "可咨询"
        return None

    def _assess_external_document_suitability(
        self,
        intent: Optional[IntentType],
        profile: Dict[str, Any],
    ) -> str:
        """基于意图和画像策略给出对外文书适用性提示。"""
        strategy_text = " ".join(
            str(profile.get(field) or "")
            for field in [
                "first_judgment",
                "strategy_choice",
                "risk_communication",
                "reusable_rule",
            ]
        )
        if intent == IntentType.DOCUMENT_DRAFT:
            return "不宜直接对外发送，需律师人工审阅后使用"
        if any(keyword in strategy_text for keyword in ["补证据", "证据先行", "高风险"]):
            return "当前更适合内部研判或补证据，不宜直接生成对外法律意见"
        return "可作为内部参考，是否对外发送需结合风险等级确认"

    def _append_profile_strategy(self, output: str, context: ProcessingContext) -> str:
        """把画像策略摘要追加到输出，便于审阅和追踪。"""
        strategy = context.profile_strategy
        if not strategy:
            return output

        lines = [
            "",
            "## 【画像策略】",
            f"- 命中画像：{', '.join(strategy.get('record_ids', []))}",
        ]
        if strategy.get("strategy_choice"):
            lines.append(f"- 策略选择：{strategy['strategy_choice']}")
        if strategy.get("risk_communication"):
            lines.append(f"- 风险沟通：{strategy['risk_communication']}")
        if strategy.get("handling_temperature"):
            lines.append(f"- 处理温度：{strategy['handling_temperature']}")
        if strategy.get("reusable_rule"):
            lines.append(f"- 可复用规则：{strategy['reusable_rule']}")
        if strategy.get("external_document_suitability"):
            lines.append(f"- 对外文书适用性：{strategy['external_document_suitability']}")

        return output.rstrip() + "\n" + "\n".join(lines)
    
    async def _handle_regulation_query(
        self,
        user_input: str,
        context: ProcessingContext,
    ) -> str:
        """
        处理法规查询
        
        流程：
        1. 调用Research子Agent进行法规检索
        2. 调用引用核验工具
        3. 生成带来源的回答
        """
        context.tools_used.append("research.search_regulations")
        
        # 调用Research子Agent
        result = await self.research.search_regulations(
            query=user_input,
            context=context,
        )
        
        context.tools_used.append("research.verify_citations")
        
        return result
    
    async def _handle_case_search(
        self,
        user_input: str,
        context: ProcessingContext,
    ) -> str:
        """
        处理类案检索
        
        流程：
        1. 调用Research子Agent进行类案检索
        2. 抽取裁判要旨
        3. 返回案例摘要
        """
        context.tools_used.append("research.search_cases")
        
        result = await self.research.search_cases(
            description=user_input,
            context=context,
        )
        
        context.tools_used.append("research.extract_summaries")
        
        return result
    
    async def _handle_document_draft(
        self,
        user_input: str,
        context: ProcessingContext,
    ) -> str:
        """
        处理文书初稿生成
        
        流程：
        1. 解析用户输入，提取案件信息
        2. 调用Document子Agent生成初稿
        3. 检测缺失材料
        4. 返回初稿和待补材料清单
        """
        context.tools_used.append("document.parse_case_info")
        context.tools_used.append("document.generate_draft")
        
        result = await self.document.generate_draft(
            user_input=user_input,
            context=context,
        )
        
        return result
    
    async def _handle_contract_review(
        self,
        user_input: str,
        context: ProcessingContext,
    ) -> str:
        """
        处理合同审查
        
        流程：
        1. 解析合同内容
        2. 调用Research子Agent进行条款检索
        3. 生成审查意见
        """
        context.tools_used.append("research.search_contract_clauses")
        context.tools_used.append("document.generate_review")
        
        result = await self.research.search_contract_clauses(
            query=user_input,
            context=context,
        )
        
        return result
    
    async def _handle_general(
        self,
        user_input: str,
        context: ProcessingContext,
    ) -> str:
        """处理通用法律问题"""
        if self.llm:
            context.tools_used.append("llm.generate_general_answer")
            prompt = f"""
请回答以下用户输入，作为律师内部工作参考。

用户输入：
{user_input}

要求：
1. 如果问题不是法律问题，也可以正常简洁回应。
2. 如果涉及法律问题，必须提示需要结合具体事实和证据。
3. 不得声称已经检索法规或案例，除非输入中已经提供。
4. 不得生成可直接对外发送的正式法律意见。
5. 输出结构尽量简洁，使用中文。
"""
            try:
                answer = await self.llm.call(
                    prompt,
                    system_prompt=(
                        "你是律师工作台里的内部辅助助手。"
                        "你只能提供内部参考，不替代律师判断。"
                    ),
                    temperature=0.3,
                )
                if answer.strip():
                    return answer.strip()
            except Exception as exc:
                context.tools_used.append(f"llm.general_failed:{type(exc).__name__}")

        return f"我收到了您的问题：{user_input}\n\n抱歉，目前我专注于以下三类任务：\n1. 法规速查\n2. 类案检索\n3. 文书初稿生成\n\n请尝试重新描述您的问题，或使用指令菜单：\n- /查法规\n- /找案例\n- /写文书"
    
    async def _log_audit(self, context: ProcessingContext):
        """记录审计日志"""
        tools_used = list(context.tools_used)
        tools_used.extend(
            f"client_profile:{record_id}" for record_id in context.profile_record_ids
        )
        audit_log = AuditLog(
            task_id=context.request_id,
            session_id=context.session_id,
            trace_id=context.trace_id,
            user_id=context.user_id,
            intent=str(context.intent.value) if context.intent else "unknown",
            input_summary=context.user_input[:100] if context.user_input else "",
            tools_used=",".join(tools_used),
            output_summary=context.final_output[:200] if context.final_output else "",
            risk_level=str(context.risk_level.value) if context.risk_level else "unknown",
            confirmed=context.confirmed,
            exported=context.exported,
        )
        
        await self.audit_logger.log(audit_log)


# ===== 导出标准响应格式 =====

def format_response(
    conclusion: str,
    legal_basis: List[Dict[str, str]],
    references: List[Dict[str, str]] = None,
    risk_level: RiskLevel = RiskLevel.LOW,
    confidence: str = "中",
    additional_info: Dict[str, Any] = None,
) -> str:
    """
    格式化标准响应
    
    固定格式：
    1. 结论摘要
    2. 法律依据
    3. 相关参考
    4. 风险提示
    5. 置信度
    6. 免责声明
    """
    references = references or []
    additional_info = additional_info or {}
    
    response = f"""
## 【结论】
{conclusion}

## 【依据】
"""
    
    for i, basis in enumerate(legal_basis, 1):
        response += f"{i}. {basis.get('title', '')}"
        if basis.get('article'):
            response += f" 第{basis['article']}条"
        if basis.get('note'):
            response += f" ({basis['note']})"
        response += "\n"
    
    if references:
        response += "\n## 【相关参考】\n"
        for ref in references:
            response += f"- {ref.get('title', '')}"
            if ref.get('court'):
                response += f" ({ref['court']})"
            response += "\n"
    
    if additional_info.get('missing_items'):
        response += "\n## 【待补材料】\n"
        for item in additional_info['missing_items']:
            response += f"- {item}\n"
    
    response += f"""
## 【风险提示】
{_get_risk_message(risk_level)}

## 【置信度】
{confidence}

## 【免责声明】
本内容由AI辅助生成，仅供内部工作参考，不构成正式法律意见。
如有疑问，请咨询执业律师。
"""
    
    return response.strip()


def _get_risk_message(risk_level: RiskLevel) -> str:
    """获取风险提示"""
    messages = {
        RiskLevel.LOW: "本回答涉及一般法律信息，风险较低。建议结合具体案情进一步确认。",
        RiskLevel.MEDIUM: "本回答涉及类案分析或合同条款建议，存在一定风险。请在正式使用前咨询执业律师。",
        RiskLevel.HIGH: "⚠️ 本回答涉及诉讼策略或期限判断，风险较高。强烈建议在使用前咨询执业律师。",
    }
    return messages.get(risk_level, "风险等级未知，请谨慎使用。")
