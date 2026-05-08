"""
意图识别测试
"""

import pytest
from law_agent.intent import IntentRecognizer, IntentType


class TestIntentRecognition:
    """意图识别测试"""
    
    @pytest.fixture
    def recognizer(self):
        return IntentRecognizer()
    
    @pytest.mark.asyncio
    async def test_regulation_query(self, recognizer):
        """测试法规查询意图识别"""
        result = await recognizer.recognize(
            "公司拖欠工资三个月，员工是否可以立即解除劳动合同？"
        )
        
        assert result.intent == IntentType.REGULATION_QUERY
        assert result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_case_search(self, recognizer):
        """测试类案检索意图识别"""
        result = await recognizer.recognize(
            "帮我找建设工程领域关于实际施工人主张工程价款的案例"
        )
        
        assert result.intent == IntentType.CASE_SEARCH
        assert result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_document_draft(self, recognizer):
        """测试文书生成意图识别"""
        result = await recognizer.recognize(
            "生成一份民事起诉状"
        )
        
        assert result.intent == IntentType.DOCUMENT_DRAFT
        assert result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_unknown_intent(self, recognizer):
        """测试未知意图"""
        result = await recognizer.recognize("你好")
        
        assert result.intent == IntentType.UNKNOWN
        assert result.confidence == 0.0
