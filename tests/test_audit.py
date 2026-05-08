"""
审计日志测试
"""

import pytest
from datetime import datetime
from law_agent.audit import AuditLogger, AuditLog


class TestAuditLogger:
    """审计日志测试"""
    
    @pytest.fixture
    def logger(self):
        return AuditLogger(":memory:")
    
    @pytest.mark.asyncio
    async def test_log(self, logger):
        """测试记录日志"""
        audit_log = AuditLog(
            task_id="test_task_1",
            session_id="session_1",
            trace_id="trace_1",
            user_id="user_1",
            intent="regulation_query",
            input_summary="测试输入",
            output_summary="测试输出",
            tools_used="tool1,tool2",
            risk_level="low",
        )
        
        await logger.log(audit_log)
        
        # 查询验证
        logs = await logger.query(user_id="user_1")
        
        assert len(logs) >= 1
        assert logs[0].task_id == "test_task_1"
    
    @pytest.mark.asyncio
    async def test_statistics(self, logger):
        """测试统计功能"""
        stats = await logger.get_statistics()
        
        assert "total_tasks" in stats
        assert "intent_stats" in stats
        assert "risk_stats" in stats
