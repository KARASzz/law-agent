"""
Research子Agent

负责：
1. 法规检索
2. 类案检索
3. 引用核验
4. 裁判要旨抽取

注意：这就是一个普通的类，不是独立服务
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..tools.rag_client import RAGClient
from ..tools.regulation import RegulationSearchTool
from ..tools.case_search import CaseSearchTool
from ..tools.citation import CitationVerifyTool
from ..risk import RiskLevel

if TYPE_CHECKING:
    from ..orchestrator import ProcessingContext


class ResearchAgent:
    """
    研究子Agent
    
    提供法规和案例研究能力
    """
    
    def __init__(
        self,
        rag_client: RAGClient,
        llm_client: Optional[Any] = None,
        external_research_tool: Optional[Any] = None,
    ):
        """
        初始化Research子Agent
        
        Args:
            rag_client: RAG客户端
            llm_client: LLM客户端（可选）
        """
        self.rag = rag_client
        self.llm = llm_client
        self.external_research_tool = external_research_tool
        
        # 初始化工具
        self.regulation_tool = RegulationSearchTool(rag_client)
        self.case_tool = CaseSearchTool(rag_client, llm_client)
        self.citation_tool = CitationVerifyTool(rag_client)
    
    async def search_regulations(
        self,
        query: str,
        context: ProcessingContext,
        jurisdiction: Optional[str] = None,
    ) -> str:
        """
        检索法规并生成回答
        
        Args:
            query: 检索query
            context: 处理上下文
            jurisdiction: 法域（可选）
            
        Returns:
            str: 格式化后的回答
        """
        from ..orchestrator import format_response

        # Step 1: 检索法规
        regulation_result = await self.regulation_tool.execute(
            query=query,
            jurisdiction=jurisdiction,
            effective_only=True,
            top_k=5,
        )
        
        if not regulation_result.success:
            return f"法规检索失败：{regulation_result.error}"
        
        regulations = regulation_result.data
        
        # Step 2: 提取引用用于核验
        citations = [
            f"{reg.title} {reg.article}" 
            for reg in regulations 
            if reg.article
        ]
        
        # Step 3: 核验引用（可选，取决于配置）
        verified_regs = regulations
        if citations and self.citation_tool:
            verify_result = await self.citation_tool.execute(citations, jurisdiction)
            if verify_result.success:
                # 过滤掉无效引用
                verified_regs = [
                    reg for reg, verify in zip(regulations, verify_result.data)
                    if verify.is_valid
                ]
        
        # Step 4: 生成结论
        conclusion = await self._generate_conclusion(query, verified_regs, context)
        
        # Step 5: 格式化输出
        legal_basis = [
            {
                "title": reg.title,
                "article": reg.article,
                "note": reg.effective_status,
            }
            for reg in verified_regs
        ]
        
        response = format_response(
            conclusion=conclusion,
            legal_basis=legal_basis,
            risk_level=RiskLevel.LOW,
            confidence="中",
        )
        
        return response
    
    async def _generate_conclusion(
        self,
        query: str,
        regulations: List[Any],
        context: "ProcessingContext",
    ) -> str:
        """生成结论"""
        if not regulations:
            external_section = await self._external_research_section(
                query=query,
                purpose="legal_source_check",
                context=context,
            )
            if external_section:
                return (
                    "当前本地法规知识库未检索到可引用法规材料。"
                    "以下为联网补充检索线索，需律师核验后使用。\n\n"
                    f"{external_section}"
                )
            if self.llm:
                context.tools_used.append("llm.generate_regulation_answer")
                prompt = f"""
当前本地法规知识库没有检索到可引用材料。请基于一般法律常识，对用户问题提供内部参考性分析。

用户问题：
{query}

要求：
1. 开头明确说明“当前未检索到可引用法规材料”。
2. 不得编造具体法条编号、案例名称或裁判观点。
3. 给出下一步补充事实、证据或检索方向。
4. 不得输出正式法律意见。
"""
                try:
                    return await self.llm.call(
                        prompt,
                        system_prompt=(
                            "你是法律检索兜底助手。没有给定法规材料时，"
                            "只能给内部参考和检索方向，不能伪造依据。"
                        ),
                        temperature=0.3,
                    )
                except Exception as exc:
                    context.tools_used.append(f"llm.regulation_answer_failed:{type(exc).__name__}")
                    pass
            return "根据当前知识库，未找到相关法律规定。"

        if self.llm:
            context.tools_used.append("llm.generate_regulation_answer")
            refs = [
                {
                    "title": reg.title,
                    "article": reg.article,
                    "content": reg.content[:800],
                    "effective_status": reg.effective_status,
                }
                for reg in regulations
            ]
            prompt = f"""
请仅根据以下检索到的法规材料，回答用户问题。

用户问题：
{query}

法规材料 JSON：
{json.dumps(refs, ensure_ascii=False)}

要求：
1. 不得引用材料之外的法规或事实。
2. 如果材料不足，请明确说明“当前检索材料不足”。
3. 输出一段简洁结论，供律师内部参考。
"""
            try:
                return await self.llm.call(
                    prompt,
                    system_prompt="你是法律检索结果整理助手，只能基于给定材料总结。",
                    temperature=0.2,
                )
            except Exception as exc:
                context.tools_used.append(f"llm.regulation_answer_failed:{type(exc).__name__}")
                pass
        
        # 基于检索结果生成简要结论
        return f"根据检索结果，找到 {len(regulations)} 条相关法规建议参考。"
    
    async def search_cases(
        self,
        description: str,
        context: ProcessingContext,
        jurisdiction: Optional[str] = None,
        court_level: Optional[str] = None,
    ) -> str:
        """
        检索类案并生成回答
        
        Args:
            description: 案情描述
            context: 处理上下文
            jurisdiction: 地域（可选）
            court_level: 法院层级（可选）
            
        Returns:
            str: 格式化后的回答
        """
        # Step 1: 检索类案
        case_result = await self.case_tool.execute(
            description=description,
            jurisdiction=jurisdiction,
            court_level=court_level,
            top_k=5,
        )
        
        if not case_result.success:
            return f"类案检索失败：{case_result.error}"
        
        cases = case_result.data

        if not cases:
            external_section = await self._external_research_section(
                query=description,
                purpose="legal_source_check",
                context=context,
            )
            if external_section:
                return (
                    "当前本地类案库未检索到可引用类案材料。"
                    "以下为联网补充检索线索，需律师核验后使用。\n\n"
                    f"{external_section}"
                )

        if not cases and self.llm:
            context.tools_used.append("llm.generate_case_search_fallback")
            prompt = f"""
当前本地类案库没有检索到案例。请根据用户描述，提供内部参考性的类案检索思路和风险提示。

用户描述：
{description}

要求：
1. 开头明确说明“当前未检索到可引用类案材料”。
2. 不得编造案例、案号、法院或裁判结果。
3. 给出建议检索关键词、争议焦点和需要补充的事实。
4. 不得输出正式法律意见。
"""
            try:
                answer = await self.llm.call(
                    prompt,
                    system_prompt="你是类案检索兜底助手，不能伪造案例。",
                    temperature=0.3,
                )
                if answer.strip():
                    return answer.strip()
            except Exception:
                context.tools_used.append("llm.case_search_fallback_failed")
        
        # Step 2: 格式化输出
        references = [
            {
                "title": case.title,
                "court": case.court,
                "gist": case.gist[:200] + "..." if len(case.gist) > 200 else case.gist,
            }
            for case in cases
        ]
        
        response = self.case_tool.format_results(cases)
        
        return response
    
    async def verify_citations(
        self,
        citations: List[str],
        jurisdiction: Optional[str] = None,
    ) -> str:
        """
        核验引用
        
        Args:
            citations: 引用列表
            jurisdiction: 法域（可选）
            
        Returns:
            str: 核验结果
        """
        result = await self.citation_tool.execute(citations, jurisdiction)
        
        if result.success:
            return self.citation_tool.format_results(result.data)
        else:
            return f"引用核验失败：{result.error}"
    
    async def search_contract_clauses(
        self,
        query: str,
        context: ProcessingContext,
    ) -> str:
        """
        检索合同条款
        
        Args:
            query: 检索query
            context: 处理上下文
            
        Returns:
            str: 检索结果
        """
        # 调用RAG库的条款检索
        docs = await self.rag.search_clauses(query=query, top_k=5)
        
        if not docs:
            external_section = await self._external_research_section(
                query=query,
                purpose="legal_source_check",
                context=context,
            )
            if external_section:
                return (
                    "当前本地合同条款库未检索到可引用材料。"
                    "以下为联网补充检索线索，需律师核验后使用。\n\n"
                    f"{external_section}"
                )
            if self.llm:
                context.tools_used.append("llm.generate_contract_review_fallback")
                prompt = f"""
当前本地合同条款库没有检索到可引用材料。请根据用户输入，生成内部参考性的合同审查提示。

用户输入：
{query}

要求：
1. 开头明确说明“当前未检索到可引用合同条款材料”。
2. 不得编造具体法规、案例或模板来源。
3. 从条款完整性、履行风险、违约责任、解除条件、争议解决等角度给出审查清单。
4. 不得输出正式法律意见。
"""
                try:
                    answer = await self.llm.call(
                        prompt,
                        system_prompt="你是合同审查兜底助手，只提供内部审查清单。",
                        temperature=0.3,
                    )
                    if answer.strip():
                        return answer.strip()
                except Exception:
                    context.tools_used.append("llm.contract_review_fallback_failed")
            return "未找到相关合同条款。"
        
        # 格式化结果
        text = "## 相关合同条款参考\n\n"
        for i, doc in enumerate(docs, 1):
            text += f"### {i}. {doc.title}\n\n"
            text += f"{doc.content}\n\n"
            text += f"来源：{doc.source}\n\n"
            text += "---\n\n"
        
        return text

    async def external_research(
        self,
        query: str,
        context: ProcessingContext,
        purpose: str = "quick_search",
        urls: Optional[List[str]] = None,
        site_url: str = "",
        providers: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        freshness: str = "",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """显式调用联网研究工具，供 API 层复用。"""
        if not self.external_research_tool:
            return {
                "success": False,
                "error": "external research is not configured",
            }
        result = await self.external_research_tool.execute(
            query=query,
            purpose=purpose,
            urls=urls or [],
            site_url=site_url,
            providers=providers or [],
            max_results=max_results,
            freshness=freshness,
            include_domains=include_domains or [],
            exclude_domains=exclude_domains or [],
        )
        if result.success and isinstance(result.data, dict):
            if context is not None:
                context.tools_used.extend(
                    f"external.{call.get('provider')}.{call.get('tool')}"
                    for call in result.data.get("tool_calls", [])
                    if call.get("status") == "ok"
                )
        return result.data if result.success else {"success": False, "error": result.error}

    async def _external_research_section(
        self,
        query: str,
        purpose: str,
        context: "ProcessingContext",
    ) -> str:
        """生成联网补充资料段落，不写入已核验法律依据。"""
        if not self.external_research_tool:
            return ""
        result = await self.external_research_tool.execute(
            query=query,
            purpose=purpose,
            max_results=5,
        )
        if not result.success or not isinstance(result.data, dict):
            if result.error and context is not None:
                context.tools_used.append(f"external.research_failed:{result.error}")
            return ""

        data = result.data
        if context is not None:
            context.tools_used.extend(
                f"external.{call.get('provider')}.{call.get('tool')}"
                for call in data.get("tool_calls", [])
                if call.get("status") == "ok"
            )
        return self._format_external_research(data)

    def _format_external_research(self, data: Dict[str, Any]) -> str:
        """把联网研究结果格式化为安全的内部线索。"""
        lines = ["## 联网补充资料（需核验）"]
        answer = str(data.get("answer") or "").strip()
        if answer:
            lines.extend(["", answer])

        sources = data.get("sources") or []
        if sources:
            lines.append("")
            for index, source in enumerate(sources[:8], 1):
                title = source.get("title") or source.get("url") or "未命名来源"
                provider = source.get("provider") or "-"
                tool = source.get("tool") or "-"
                url = source.get("url") or ""
                snippet = (
                    source.get("snippet")
                    or source.get("content")
                    or ""
                ).strip()
                lines.append(f"{index}. {title}")
                if url:
                    lines.append(f"   来源链接：{url}")
                lines.append(f"   工具：{provider}/{tool}")
                if snippet:
                    lines.append(f"   摘要：{snippet[:220]}")

        warnings = data.get("warnings") or []
        lines.extend(["", "注意：联网资料仅供检索线索和内部研究，不替代本地知识库、引用核验或律师人工审阅。"])
        for warning in warnings:
            lines.append(f"- {warning}")
        return "\n".join(lines).strip()


# ===== 便捷函数 =====

async def quick_search_regulations(
    query: str,
    rag_client: RAGClient,
    **kwargs,
) -> str:
    """
    快速法规检索
    
    Args:
        query: 检索query
        rag_client: RAG客户端
        **kwargs: 其他参数
        
    Returns:
        str: 格式化后的回答
    """
    agent = ResearchAgent(rag_client)
    return await agent.search_regulations(query, None, **kwargs)


async def quick_search_cases(
    description: str,
    rag_client: RAGClient,
    **kwargs,
) -> str:
    """
    快速类案检索
    
    Args:
        description: 案情描述
        rag_client: RAG客户端
        **kwargs: 其他参数
        
    Returns:
        str: 格式化后的回答
    """
    agent = ResearchAgent(rag_client)
    return await agent.search_cases(description, None, **kwargs)
