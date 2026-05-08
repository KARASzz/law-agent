"""
律师智能体 (Law Agent)
基于自研轻量编排的法律AI工作流系统

核心模块：
- orchestrator: 主编排器
- intent: 意图识别
- risk: 风险分级
- audit: 审计日志
"""

__version__ = "0.1.0"
__author__ = "Law Agent Team"

from .orchestrator import LawOrchestrator
from .intent import IntentRecognizer
from .risk import RiskLabeler
from .audit import AuditLogger

__all__ = [
    "LawOrchestrator",
    "IntentRecognizer", 
    "RiskLabeler",
    "AuditLogger",
]
