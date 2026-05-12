"""
工具层 (Tools)

职责：
1. 提供各类工具能力的抽象接口
2. 工具注册和调用机制
3. RAG库对接

工具列表：
- regulation: 法规检索
- case_search: 类案检索
- citation: 引用核验
- document: 文书生成
- rag_client: RAG库客户端
"""

from .base import BaseTool, ToolResult, ToolRegistry
from .regulation import RegulationSearchTool
from .case_search import CaseSearchTool
from .citation import CitationVerifyTool
from .document import DocumentTool
from .rag_client import RAGClient
from .external_research import (
    ExternalResearchTool,
    create_external_research_tool,
)

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "RegulationSearchTool",
    "CaseSearchTool",
    "CitationVerifyTool",
    "DocumentTool",
    "RAGClient",
    "ExternalResearchTool",
    "create_external_research_tool",
]
