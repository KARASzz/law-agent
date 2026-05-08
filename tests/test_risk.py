"""
风险评估测试
"""

import pytest
from law_agent.risk import RiskLabeler, RiskLevel
from law_agent.intent import IntentType


class TestRiskLabeling:
    """风险评估测试"""
    
    @pytest.fixture
    def labeler(self):
        return RiskLabeler()
    
    @pytest.mark.asyncio
    async def test_low_risk_regulation(self, labeler):
        """测试低风险法规查询"""
        level = await labeler.label(
            intent=IntentType.REGULATION_QUERY,
            content="根据劳动合同法第38条..."
        )
        
        assert level == RiskLevel.LOW
    
    @pytest.mark.asyncio
    async def test_high_risk_document(self, labeler):
        """测试高风险文书生成"""
        level = await labeler.label(
            intent=IntentType.DOCUMENT_DRAFT,
            content="起诉状..."
        )
        
        assert level == RiskLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_risk_with_amount(self, labeler):
        """测试涉及金额的风险评估"""
        level = await labeler.label(
            intent=IntentType.DOCUMENT_DRAFT,
            content="赔偿100万元",
            metadata={"amount": 1000000}
        )
        
        assert level == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_medium_risk_export_requires_confirmation(self, labeler):
        """中风险内容确认前不能对外导出。"""
        result = await labeler.label_detailed(
            intent=IntentType.CASE_SEARCH,
            content="提供类似案例参考",
        )

        assert result.requires_confirmation is True
        assert result.can_export is False

        confirmed = await labeler.label_detailed(
            intent=IntentType.CASE_SEARCH,
            content="提供类似案例参考",
            metadata={"confirmed": True},
        )

        assert confirmed.can_export is True
