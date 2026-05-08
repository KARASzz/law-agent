"""
类案检索工具

提供类案检索能力，包括：
1. 自然语言检索
2. 案由/争点提取
3. 裁判要旨抽取
4. 地域/法院层级过滤
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import BaseTool, ToolResult, ToolType
from .rag_client import RAGClient, RAGDocument


@dataclass
class CaseResult:
    """类案检索结果"""
    id: str
    case_number: str  # 案号
    title: str  # 案件标题
    court: str  # 审理法院
    judge_date: str  # 裁判日期
    case_type: str  # 案件类型
    case_reason: str  # 案由
    gist: str  # 裁判要旨
    legal_basis: List[str]  # 法律依据
    judgment_result: str  # 裁判结果
    relevance_score: float  # 相关度评分
    jurisdiction: str  # 地域


class CaseSearchTool(BaseTool):
    """
    类案检索工具
    
    提供：
    1. 自然语言检索案例
    2. 裁判要旨抽取
    3. 地域/法院层级过滤
    """
    
    name = "search_cases"
    description = "根据案情描述检索相关案例，返回裁判要旨和裁判结果"
    tool_type = ToolType.CASE
    
    def __init__(
        self,
        rag_client: RAGClient,
        llm_client: Optional[Any] = None,
    ):
        """
        初始化类案检索工具
        
        Args:
            rag_client: RAG客户端
            llm_client: LLM客户端（用于抽取裁判要旨）
        """
        self.rag = rag_client
        self.llm = llm_client
    
    async def execute(
        self,
        description: str,
        case_reason: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        court_level: Optional[str] = None,
        top_k: int = 5,
    ) -> ToolResult:
        """
        执行类案检索
        
        Args:
            description: 案情描述
            case_reason: 案由（可选）
            jurisdiction: 地域（可选）
            court_level: 法院层级（可选）
            top_k: 返回数量
            
        Returns:
            ToolResult: 检索结果
        """
        try:
            # 构建检索query
            query = description
            if case_reason:
                query = f"{case_reason} - {description}"
            
            # 调用RAG库检索
            docs = await self.rag.search_cases(
                query=query,
                jurisdiction=jurisdiction,
                court_level=court_level,
                top_k=top_k,
            )
            
            # 转换为CaseResult
            results = []
            for doc in docs:
                case = self._doc_to_case(doc)
                results.append(case)
            
            # 如果有LLM，可以进一步抽取裁判要旨
            if self.llm and results:
                results = await self._extract_gist_with_llm(results, description)
            
            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "query": description,
                    "case_reason": case_reason,
                    "count": len(results),
                    "jurisdiction": jurisdiction,
                },
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"类案检索失败: {str(e)}",
            )
    
    def _doc_to_case(self, doc: RAGDocument) -> CaseResult:
        """将RAG文档转换为案例结果"""
        # 从metadata提取字段
        metadata = doc.metadata or {}
        
        return CaseResult(
            id=doc.id,
            case_number=metadata.get("case_number", ""),
            title=doc.title,
            court=metadata.get("court", ""),
            judge_date=metadata.get("judge_date", ""),
            case_type=metadata.get("case_type", ""),
            case_reason=metadata.get("case_reason", ""),
            gist=doc.content,  # 默认使用全文，后续LLM抽取
            legal_basis=metadata.get("legal_basis", []),
            judgment_result=metadata.get("judgment_result", ""),
            relevance_score=doc.relevance_score,
            jurisdiction=doc.jurisdiction or "未知",
        )
    
    async def _extract_gist_with_llm(
        self,
        cases: List[CaseResult],
        description: str,
    ) -> List[CaseResult]:
        """
        使用LLM抽取裁判要旨
        
        Args:
            cases: 案例列表
            description: 原始案情描述
            
        Returns:
            List[CaseResult]: 抽取后的案例
        """
        # TODO: 实现LLM裁判要旨抽取
        # 简化处理：直接返回原始结果
        return cases
    
    def format_results(self, cases: List[CaseResult], show_disclaimer: bool = True) -> str:
        """
        格式化检索结果为文本
        
        Args:
            cases: 案例列表
            show_disclaimer: 是否显示免责声明
            
        Returns:
            str: 格式化文本
        """
        if not cases:
            return "未找到相关案例"
        
        text = ""
        for i, case in enumerate(cases, 1):
            text += f"### 【案例 {i}】{case.title}\n\n"
            
            if case.case_number:
                text += f"- **案号**: {case.case_number}\n"
            if case.court:
                text += f"- **审理法院**: {case.court}\n"
            if case.judge_date:
                text += f"- **裁判日期**: {case.judge_date}\n"
            if case.case_reason:
                text += f"- **案由**: {case.case_reason}\n"
            if case.relevance_score:
                text += f"- **相关度**: {case.relevance_score:.2f}\n"
            
            text += f"\n**裁判要旨**:\n{case.gist}\n\n"
            
            if case.legal_basis:
                text += f"**法律依据**: {', '.join(case.legal_basis)}\n\n"
            
            if case.judgment_result:
                text += f"**裁判结果**: {case.judgment_result}\n\n"
            
            text += "---\n\n"
        
        if show_disclaimer:
            text += """
---
⚠️ **免责声明**: 以上案例仅供参考，不构成法律意见。
实际案件处理请结合具体案情，并咨询执业律师。
"""
        
        return text.strip()


# ===== 便捷函数 =====

async def search_cases(
    description: str,
    rag_client: RAGClient,
    **kwargs,
) -> List[CaseResult]:
    """
    快速检索类案
    
    Args:
        description: 案情描述
        rag_client: RAG客户端
        **kwargs: 其他参数
        
    Returns:
        List[CaseResult]: 检索结果
    """
    tool = CaseSearchTool(rag_client)
    result = await tool.execute(description, **kwargs)
    
    if result.success:
        return result.data
    return []
