"""
子Agent模块

职责：
1. Research子Agent - 负责法规检索、类案检索、引用核验
2. Document子Agent - 负责文书生成、合同审查

注意：这些不是独立的Agent服务，就是普通的Python类/函数
"""

from .research import ResearchAgent
from .document_agent import DocumentAgent

__all__ = [
    "ResearchAgent",
    "DocumentAgent",
]
