"""
风险分级模块 (Risk Labeling)

职责：
1. 根据意图类型和输出内容判定风险等级
2. 生成风险提示

风险等级：
- LOW: 低风险（一般法律信息整理）
- MEDIUM: 中风险（类案分析、合同条款建议）
- HIGH: 高风险（诉讼策略、对外文书、期限判断）
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional

from .intent import IntentType


class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"       # 低风险
    MEDIUM = "medium" # 中风险
    HIGH = "high"    # 高风险


@dataclass
class RiskResult:
    """风险评估结果"""
    level: RiskLevel
    message: str
    requires_confirmation: bool = False  # 是否需要人工确认
    can_export: bool = True  # 是否可以导出


# ===== 风险判定规则 =====

class RiskLabeler:
    """
    风险标签器
    
    根据以下维度判定风险：
    1. 意图类型
    2. 内容特征词
    3. 涉及金额
    4. 程序期限
    """
    
    # 高风险关键词
    HIGH_RISK_KEYWORDS = [
        "诉讼", "起诉", "上诉", "申诉",
        "判决", "裁定", "裁决",
        "期限", "时效", "截止",
        "赔偿", "赔偿金", "违约金",
        "刑事责任", "刑事拘留", "逮捕",
        "无效", "撤销", "解除",
    ]
    
    # 中风险关键词
    MEDIUM_RISK_KEYWORDS = [
        "案例", "参考", "类似",
        "合同", "条款", "协议",
        "风险", "建议", "审查",
        "律师函", "催告", "通知",
    ]

    RISK_ORDER = {
        RiskLevel.LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3,
    }
    
    def __init__(self, llm_client: Optional[Any] = None):
        self.llm = llm_client
    
    async def label(
        self,
        intent: IntentType,
        content: str,
        metadata: Optional[dict] = None,
    ) -> RiskLevel:
        """
        判定风险等级
        
        Args:
            intent: 意图类型
            content: 输出内容
            metadata: 额外元数据
            
        Returns:
            RiskLevel: 风险等级
        """
        metadata = metadata or {}
        
        # Step 1: 根据意图确定基础风险
        base_risk = self._get_base_risk(intent)
        
        # Step 2: 根据内容特征词调整风险
        content_risk = self._analyze_content(content, intent)
        
        # Step 3: 根据元数据调整风险
        meta_risk = self._analyze_metadata(metadata)
        
        # 综合判定（取最高风险）
        final_risk = max(
            base_risk,
            content_risk,
            meta_risk,
            key=lambda level: self.RISK_ORDER[level],
        )
        
        return final_risk
    
    def _get_base_risk(self, intent: IntentType) -> RiskLevel:
        """根据意图类型确定基础风险"""
        risk_map = {
            IntentType.REGULATION_QUERY: RiskLevel.LOW,
            IntentType.CASE_SEARCH: RiskLevel.MEDIUM,
            IntentType.DOCUMENT_DRAFT: RiskLevel.HIGH,
            IntentType.CONTRACT_REVIEW: RiskLevel.MEDIUM,
            IntentType.GENERAL: RiskLevel.LOW,
            IntentType.UNKNOWN: RiskLevel.LOW,
        }
        return risk_map.get(intent, RiskLevel.LOW)
    
    def _analyze_content(self, content: str, intent: IntentType) -> RiskLevel:
        """分析内容中的风险关键词"""
        content_lower = content.lower()
        
        # 检查高风险关键词
        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword in content_lower:
                return RiskLevel.HIGH
        
        # 法规查询里常会自然出现“合同/条款/参考”等词，不单独抬高中风险。
        if intent != IntentType.REGULATION_QUERY:
            for keyword in self.MEDIUM_RISK_KEYWORDS:
                if keyword in content_lower:
                    return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _analyze_metadata(self, metadata: dict) -> RiskLevel:
        """分析元数据中的风险因素"""
        # 如果涉及金额较大
        amount = metadata.get("amount", 0)
        if amount > 100000:  # 10万以上
            return RiskLevel.HIGH
        elif amount > 10000:  # 1万以上
            return RiskLevel.MEDIUM
        
        # 如果涉及程序期限
        if metadata.get("has_deadline"):
            return RiskLevel.HIGH
        
        # 如果涉及对外出具
        if metadata.get("is_external"):
            return RiskLevel.HIGH
        
        return RiskLevel.LOW
    
    async def label_detailed(
        self,
        intent: IntentType,
        content: str,
        metadata: Optional[dict] = None,
    ) -> RiskResult:
        """
        详细风险评估
        
        返回完整的风险评估结果
        """
        metadata = metadata or {}
        level = await self.label(intent, content, metadata)
        
        # 生成风险消息
        message = self._generate_message(level, intent)
        
        # 判定是否需要确认
        requires_confirmation = level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
        
        # 判定是否可以导出：中高风险必须人工确认后才能对外使用。
        can_export = not requires_confirmation or metadata.get("confirmed", False)
        
        return RiskResult(
            level=level,
            message=message,
            requires_confirmation=requires_confirmation,
            can_export=can_export,
        )
    
    def _generate_message(self, level: RiskLevel, intent: IntentType) -> str:
        """生成风险提示消息"""
        messages = {
            (RiskLevel.LOW, IntentType.REGULATION_QUERY):
                "本回答涉及一般法律信息解读，风险较低。",
            (RiskLevel.LOW, IntentType.GENERAL):
                "本回答提供一般性法律信息，风险较低。",
            (RiskLevel.MEDIUM, IntentType.CASE_SEARCH):
                "本回答提供类案分析供参考，请结合具体案情判断。",
            (RiskLevel.MEDIUM, IntentType.CONTRACT_REVIEW):
                "本回答提供合同条款审查意见，建议在使用前确认。",
            (RiskLevel.HIGH, IntentType.DOCUMENT_DRAFT):
                "⚠️ 文书初稿未经确认，请务必人工审阅后再使用。",
        }
        
        # 尝试获取特定消息
        specific_msg = messages.get((level, intent))
        if specific_msg:
            return specific_msg
        
        # 返回通用消息
        generic_messages = {
            RiskLevel.LOW: "风险较低，可直接参考使用。",
            RiskLevel.MEDIUM: "存在一定风险，建议在使用前进一步确认。",
            RiskLevel.HIGH: "⚠️ 风险较高，请务必咨询执业律师后使用。",
        }
        return generic_messages[level]


# ===== 快捷函数 =====

async def quick_label(
    intent: IntentType,
    content: str,
) -> RiskLevel:
    """快速风险评估"""
    labeler = RiskLabeler()
    return await labeler.label(intent, content)
