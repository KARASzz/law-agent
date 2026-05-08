"""
引用核验工具

提供法律引用核验能力，包括：
1. 法条编号验证
2. 引用准确性验证
3. 失效状态检查
4. 法域匹配检查
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

from .base import BaseTool, ToolResult, ToolType
from .rag_client import RAGClient


@dataclass
class CitationVerifyResult:
    """引用核验结果"""
    citation: str  # 原始引用
    citation_type: str  # 引用类型（法律/司法解释/案例）
    title: str  # 标题
    article: str  # 条款编号
    is_valid: bool  # 是否有效
    is_accurate: bool  # 是否准确
    effective_status: str  # 有效状态
    matched_content: str  # 匹配到的内容
    issues: List[str]  # 问题列表
    suggestion: str  # 修正建议


class CitationVerifyTool(BaseTool):
    """
    引用核验工具
    
    提供：
    1. 法条编号验证
    2. 引用准确性验证
    3. 失效状态检查
    4. 法域匹配检查
    """
    
    name = "verify_citations"
    description = "核验法律引用的准确性、有效性和法域匹配性"
    tool_type = ToolType.CITATION
    
    # 常见法条编号模式
    CITATION_PATTERNS = {
        "法律": r'《([^》]+)》第([一二三四五六七八九十百千\d]+)条',
        "款": r'第([一二三四五六七八九十百千\d]+)款',
        "项": r'第([一二三四五六七八九十百千\d]+)项',
        "案例": r'([^】]+)第([零一二三四五六七八九十百千\d]+)号',
    }
    
    def __init__(
        self,
        rag_client: RAGClient,
        strict_mode: bool = False,
    ):
        """
        初始化引用核验工具
        
        Args:
            rag_client: RAG客户端
            strict_mode: 严格模式（不允许模糊匹配）
        """
        self.rag = rag_client
        self.strict_mode = strict_mode
    
    async def execute(
        self,
        citations: List[str],
        jurisdiction: Optional[str] = None,
    ) -> ToolResult:
        """
        执行引用核验
        
        Args:
            citations: 引用列表，如 ["《劳动合同法》第38条", "《民法典》第143条"]
            jurisdiction: 法域（可选）
            
        Returns:
            ToolResult: 核验结果
        """
        try:
            results = []
            issues = []
            
            for citation in citations:
                result = await self._verify_single_citation(citation, jurisdiction)
                results.append(result)
                
                if not result.is_valid or not result.is_accurate:
                    issues.extend(result.issues)
            
            return ToolResult(
                success=len(issues) == 0,
                data=results,
                metadata={
                    "total": len(citations),
                    "valid": sum(1 for r in results if r.is_valid),
                    "invalid": sum(1 for r in results if not r.is_valid),
                    "issues": issues,
                },
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"引用核验失败: {str(e)}",
            )
    
    async def _verify_single_citation(
        self,
        citation: str,
        jurisdiction: Optional[str] = None,
    ) -> CitationVerifyResult:
        """核验单个引用"""
        # 解析引用
        parsed = self._parse_citation(citation)
        
        if not parsed:
            return CitationVerifyResult(
                citation=citation,
                citation_type="unknown",
                title="",
                article="",
                is_valid=False,
                is_accurate=False,
                effective_status="未知",
                matched_content="",
                issues=[f"无法解析引用: {citation}"],
                suggestion="请检查引用格式是否正确",
            )
        
        # 在RAG库中检索验证
        search_query = f"{parsed['title']} {parsed['article']}"
        docs = await self.rag.search_regulations(
            query=search_query,
            jurisdiction=jurisdiction,
            top_k=3,
        )
        
        # 检查是否找到
        if not docs:
            return CitationVerifyResult(
                citation=citation,
                citation_type=parsed["type"],
                title=parsed["title"],
                article=parsed["article"],
                is_valid=False,
                is_accurate=False,
                effective_status="未找到",
                matched_content="",
                issues=[f"未找到对应的法律规定: {citation}"] if not self.strict_mode else [],
                suggestion=f"请确认 {parsed['title']} 是否为有效法规" if self.strict_mode else "",
            )
        
        # 匹配最佳结果
        best_match = docs[0]
        
        # 检查准确性
        is_accurate = self._check_accuracy(citation, best_match.content)
        
        # 检查有效性
        is_valid = best_match.expire_date is None
        
        # 收集问题
        issues = []
        if not is_valid:
            issues.append(f"该条款可能已失效（失效日期: {best_match.expire_date}）")
        if not is_accurate:
            issues.append("引用内容与原文存在差异")
        
        return CitationVerifyResult(
            citation=citation,
            citation_type=parsed["type"],
            title=best_match.title,
            article=parsed["article"],
            is_valid=is_valid,
            is_accurate=is_accurate,
            effective_status="有效" if is_valid else "已失效",
            matched_content=best_match.content[:500],
            issues=issues,
            suggestion="" if is_accurate else f"建议核实 {best_match.title} 的具体内容",
        )
    
    def _parse_citation(self, citation: str) -> Optional[Dict[str, str]]:
        """解析引用字符串"""
        citation = citation.strip()
        
        # 匹配法律引用：《XXX》第X条
        match = re.search(self.CITATION_PATTERNS["法律"], citation)
        if match:
            return {
                "type": "法律",
                "title": match.group(1),
                "article": f"第{match.group(2)}条",
            }
        
        # 匹配司法解释引用
        match = re.search(r'《([^》]+)》第([一二三四五六七八九十百千\d]+)条之?([一二三四五六七八九十百千\d]+)?', citation)
        if match:
            article = f"第{match.group(2)}条"
            if match.group(3):
                article += f"第{match.group(3)}款"
            return {
                "type": "司法解释",
                "title": match.group(1),
                "article": article,
            }
        
        return None
    
    def _check_accuracy(self, citation: str, content: str) -> bool:
        """检查引用准确性"""
        # 简单检查：citation中的关键词是否在content中
        citation_clean = re.sub(r'[《》]', '', citation)
        
        # 提取关键信息
        title_match = re.search(r'《([^》]+)》', citation)
        if title_match:
            title = title_match.group(1)
            if title not in content:
                return False
        
        # 提取条款编号
        article_match = re.search(r'第([一二三四五六七八九十百千\d]+)条', citation)
        if article_match:
            article = article_match.group(1)
            if f"第{article}条" not in content:
                return False
        
        return True
    
    def format_results(self, results: List[CitationVerifyResult]) -> str:
        """
        格式化核验结果
        
        Args:
            results: 核验结果列表
            
        Returns:
            str: 格式化文本
        """
        if not results:
            return "无需核验"
        
        text = "### 引用核验结果\n\n"
        
        all_valid = True
        for i, result in enumerate(results, 1):
            status = "✅" if result.is_valid and result.is_accurate else "❌"
            text += f"{status} **{result.citation}**\n"
            
            if result.title:
                text += f"   - 匹配: {result.title} {result.article}\n"
            text += f"   - 状态: {result.effective_status}\n"
            
            if result.issues:
                all_valid = False
                text += f"   - ⚠️ 问题:\n"
                for issue in result.issues:
                    text += f"     - {issue}\n"
            
            if result.suggestion:
                text += f"   - 💡 建议: {result.suggestion}\n"
            
            text += "\n"
        
        if all_valid:
            text += "\n✅ 所有引用核验通过"
        else:
            text += "\n⚠️ 部分引用存在问题，请核实后使用"
        
        return text.strip()


# ===== 便捷函数 =====

async def verify_citations(
    citations: List[str],
    rag_client: RAGClient,
    **kwargs,
) -> List[CitationVerifyResult]:
    """
    快速核验引用
    
    Args:
        citations: 引用列表
        rag_client: RAG客户端
        **kwargs: 其他参数
        
    Returns:
        List[CitationVerifyResult]: 核验结果
    """
    tool = CitationVerifyTool(rag_client)
    result = await tool.execute(citations, **kwargs)
    
    if result.success or result.data:
        return result.data
    return []
