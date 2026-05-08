"""
测试模块
"""

import pytest
import asyncio


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_rag_client():
    """模拟RAG客户端"""
    from law_agent.tools.rag_client import RAGClient, RAGDocument
    
    class MockRAGClient(RAGClient):
        async def health_check(self):
            return True
        
        async def search_regulations(self, **kwargs):
            return [
                RAGDocument(
                    id="1",
                    title="中华人民共和国劳动合同法",
                    content="第三十八条 用人单位有下列情形之一的，劳动者可以解除劳动合同：...",
                    source="全国人民代表大会",
                    source_type="law",
                    jurisdiction="全国",
                    authority_level="法律",
                    relevance_score=0.95,
                )
            ]
        
        async def search_cases(self, **kwargs):
            return [
                RAGDocument(
                    id="case1",
                    title="某公司与员工劳动合同纠纷案",
                    content="法院认为，根据劳动合同法第38条...",
                    source="中国裁判文书网",
                    source_type="case",
                    jurisdiction="北京",
                    metadata={
                        "case_number": "(2021)京01民终1234号",
                        "court": "北京市第一中级人民法院",
                        "judge_date": "2021-06-15",
                    },
                )
            ]
    
    return MockRAGClient("http://mock", "mock_key")


@pytest.fixture
async def orchestrator(mock_rag_client):
    """创建测试用编排器"""
    from law_agent import LawOrchestrator
    from law_agent.tools import ToolRegistry
    from law_agent.intent import IntentRecognizer
    from law_agent.risk import RiskLabeler
    from law_agent.audit import AuditLogger
    from law_agent.sub_agents import ResearchAgent, DocumentAgent
    
    tool_registry = ToolRegistry()
    
    audit_logger = AuditLogger(":memory:")
    
    intent_recognizer = IntentRecognizer()
    risk_labeler = RiskLabeler()
    
    research_agent = ResearchAgent(mock_rag_client)
    document_agent = DocumentAgent()
    
    return LawOrchestrator(
        llm_client=None,
        tool_registry=tool_registry,
        intent_recognizer=intent_recognizer,
        risk_labeler=risk_labeler,
        audit_logger=audit_logger,
        research_agent=research_agent,
        document_agent=document_agent,
    )
