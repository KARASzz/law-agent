"""
法规检索工具

提供法规检索能力，包括：
1. 自然语言检索
2. 精确检索
3. 法域/时间过滤
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re

from .base import BaseTool, ToolResult, ToolType
from .rag_client import RAGClient, RAGDocument
@dataclass
class RegulationResult:
    """法规检索结果"""
    id: str
    title: str
    article: str  # 条款编号
    content: str  # 条款内容
    source: str  # 来源
    effective_status: str  # 有效/失效/部分失效
    jurisdiction: str  # 全国/地方
    authority_level: str  # 法律/行政法规/司法解释
    relevance_score: float  # 相关度评分
    verified: bool = False  # 是否已核验


class RegulationSearchTool(BaseTool):
    """
    法规检索工具
    
    提供：
    1. 自然语言检索法规
    2. 法域过滤
    3. 权威等级过滤
    4. 有效性过滤
    """
    
    name = "search_regulations"
    description = "根据自然语言query检索相关法律法规和司法解释"
    tool_type = ToolType.REGULATION
    
    def __init__(
        self,
        rag_client: RAGClient,
        verify_enabled: bool = True,
    ):
        """
        初始化法规检索工具
        
        Args:
            rag_client: RAG客户端
            verify_enabled: 是否启用引用核验
        """
        self.rag = rag_client
        self.verify_enabled = verify_enabled
    
    async def execute(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        authority_level: Optional[str] = None,
        effective_only: bool = True,
        top_k: int = 5,
    ) -> ToolResult:
        """
        执行法规检索
        
        Args:
            query: 检索query
            jurisdiction: 法域（可选）
            authority_level: 权威等级（可选）
            effective_only: 仅返回有效法规
            top_k: 返回数量
            
        Returns:
            ToolResult: 检索结果
        """
        try:
            # 调用RAG库检索
            docs = await self.rag.search_regulations(
                query=query,
                jurisdiction=jurisdiction,
                authority_level=authority_level,
                effective_only=effective_only,
                top_k=top_k,
            )
            
            # 转换为RegulationResult
            results = []
            for doc in docs:
                regulation = self._doc_to_regulation(doc)
                results.append(regulation)
            
            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "query": query,
                    "count": len(results),
                    "jurisdiction": jurisdiction,
                    "authority_level": authority_level,
                },
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"法规检索失败: {str(e)}",
            )
    
    def _doc_to_regulation(self, doc: RAGDocument) -> RegulationResult:
        """将RAG文档转换为法规结果"""
        # 提取条款编号
        article = self._extract_article(doc.content)
        
        # 判断有效状态
        effective_status = self._check_effective_status(doc)
        
        return RegulationResult(
            id=doc.id,
            title=doc.title,
            article=article,
            content=doc.content,
            source=doc.source,
            effective_status=effective_status,
            jurisdiction=doc.jurisdiction or "全国",
            authority_level=doc.authority_level or "未知",
            relevance_score=doc.relevance_score,
        )
    
    def _extract_article(self, content: str) -> str:
        """从内容中提取条款编号"""
        # 常见模式：第X条、第X款、第X项
        patterns = [
            r'第([一二三四五六七八九十百千\d]+)条',
            r'第([一二三四五六七八九十百千\d]+)款',
            r'第([一二三四五六七八九十百千\d]+)项',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return f"第{match.group(1)}条"
        
        return ""
    
    def _check_effective_status(self, doc: RAGDocument) -> str:
        """检查法规有效状态"""
        if doc.expire_date:
            return "已失效"
        
        if doc.effective_date:
            return "有效"
        
        # 默认假设有效
        return "有效"
    
    def format_results(self, results: List[RegulationResult]) -> str:
        """
        格式化检索结果为文本
        
        Args:
            results: 检索结果列表
            
        Returns:
            str: 格式化文本
        """
        if not results:
            return "未找到相关法规"
        
        text = ""
        for i, reg in enumerate(results, 1):
            text += f"{i}. **{reg.title}**"
            if reg.article:
                text += f" {reg.article}"
            text += f"\n   来源: {reg.source}"
            text += f"\n   效力: {reg.effective_status}"
            text += f"\n   相关度: {reg.relevance_score:.2f}"
            text += f"\n   内容摘要: {reg.content[:200]}..."
            text += "\n\n"
        
        return text.strip()


# ===== 便捷函数 =====

async def search_regulations(
    query: str,
    rag_client: RAGClient,
    **kwargs,
) -> List[RegulationResult]:
    """
    快速检索法规
    
    Args:
        query: 检索query
        rag_client: RAG客户端
        **kwargs: 其他参数
        
    Returns:
        List[RegulationResult]: 检索结果
    """
    tool = RegulationSearchTool(rag_client)
    result = await tool.execute(query, **kwargs)
    
    if result.success:
        return result.data
    return []
