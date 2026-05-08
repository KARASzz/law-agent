"""
编排器测试
"""

import pytest


class TestOrchestrator:
    """编排器测试"""
    
    @pytest.mark.asyncio
    async def test_process_regulation_query(self, orchestrator):
        """测试处理法规查询"""
        result = await orchestrator.process(
            user_input="公司拖欠工资三个月，员工是否可以立即解除劳动合同？"
        )
        
        assert result.success
        assert result.intent.value == "regulation_query"
        assert result.risk_level.value == "low"
        assert len(result.output) > 0
    
    @pytest.mark.asyncio
    async def test_process_case_search(self, orchestrator):
        """测试处理类案检索"""
        result = await orchestrator.process(
            user_input="帮我找建设工程领域的案例"
        )
        
        assert result.success
        assert result.intent.value == "case_search"
    
    @pytest.mark.asyncio
    async def test_process_document_draft(self, orchestrator):
        """测试处理文书生成"""
        result = await orchestrator.process(
            user_input="生成一份民事起诉状"
        )
        
        assert result.success
        assert result.intent.value == "document_draft"
        assert result.risk_level.value == "high"
