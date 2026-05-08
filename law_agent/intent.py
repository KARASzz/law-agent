"""
意图识别模块 (Intent Recognition)

职责：
1. 识别用户输入的意图类型
2. 返回置信度

意图类型：
- REGULATION_QUERY: 法规查询
- CASE_SEARCH: 类案检索
- DOCUMENT_DRAFT: 文书初稿生成
- CONTRACT_REVIEW: 合同审查
- GENERAL: 通用问题
- UNKNOWN: 未知
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import re


class IntentType(Enum):
    """意图类型枚举"""
    REGULATION_QUERY = "regulation_query"      # 法规查询
    CASE_SEARCH = "case_search"                # 类案检索
    DOCUMENT_DRAFT = "document_draft"          # 文书初稿生成
    CONTRACT_REVIEW = "contract_review"        # 合同审查
    GENERAL = "general"                        # 通用问题
    UNKNOWN = "unknown"                        # 未知


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: IntentType
    confidence: float  # 0.0 - 1.0
    keywords: List[str] = None  # 触发关键词
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


# ===== 意图识别规则 =====

# 法规查询关键词
REGULATION_KEYWORDS = [
    # 疑问词
    "是否", "能否", "可否", "能不能", "是不是", "有没有",
    # 法规相关
    "法条", "法", "规定", "条款", "条文", "法规", "法律",
    "根据", "依据", "按照", "遵照", "遵循",
    # 罪名/责任
    "构成", "属于", "违法", "犯罪", "责任", "处罚",
    # 权利
    "权利", "有权", "可以", "允许", "应当", "必须",
    # 期限
    "时效", "期限", "多少天", "多久",
    # 场景
    "公司拖欠工资", "劳动合同", "解除合同", "赔偿", "补偿",
    "交通事故", "医疗事故", "工伤", "离婚", "继承",
]

# 类案检索关键词
CASE_KEYWORDS = [
    # 案例相关
    "案例", "判例", "案件", "判例法",
    # 检索要求
    "类似", "相似", "相关", "参考", "参照",
    "找", "查", "搜索", "检索",
    # 地域/层级
    "最高院", "高院", "中院", "基层法院",
    # 场景
    "实际施工人", "工程价款", "建设工程",
    "劳动争议", "工伤认定", "交通事故责任",
]

# 文书生成关键词
DOCUMENT_KEYWORDS = [
    # 文书类型
    "起诉状", "答辩状", "上诉状", "申诉状",
    "申请书", "代理词", "法律意见书", "律师函",
    # 操作
    "生成", "写", "起草", "制作",
    # 诉讼请求
    "诉讼请求", "赔偿", "补偿", "返还",
    # 当事人
    "原告", "被告", "第三人",
]

# 合同审查关键词
CONTRACT_KEYWORDS = [
    # 合同相关
    "合同", "协议", "条款", "约定",
    # 审查操作
    "审查", "审核", "检查", "风险", "漏洞",
    "合规", "效力", "有效", "无效",
    # 合同类型
    "租赁", "买卖", "借款", "劳动", "合伙",
    "投资", "股权转让", "租赁",
]


class IntentRecognizer:
    """
    意图识别器
    
    使用规则匹配 + LLM辅助识别
    优先使用规则匹配，置信度低时调用LLM
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        self.llm = llm_client
        
        # 编译正则表达式
        self._regulation_pattern = self._build_pattern(REGULATION_KEYWORDS)
        self._case_pattern = self._build_pattern(CASE_KEYWORDS)
        self._document_pattern = self._build_pattern(DOCUMENT_KEYWORDS)
        self._contract_pattern = self._build_pattern(CONTRACT_KEYWORDS)
    
    def _build_pattern(self, keywords: List[str]) -> re.Pattern:
        """构建关键词正则表达式"""
        # 转义特殊字符并用|连接
        escaped = [re.escape(k) for k in keywords]
        pattern = "|".join(escaped)
        return re.compile(pattern, re.IGNORECASE)
    
    async def recognize(self, user_input: str) -> IntentResult:
        """
        识别用户意图
        
        Args:
            user_input: 用户输入
            
        Returns:
            IntentResult: 意图识别结果
        """
        # 统计各类关键词命中数量
        regulation_matches = self._regulation_pattern.findall(user_input)
        case_matches = self._case_pattern.findall(user_input)
        document_matches = self._document_pattern.findall(user_input)
        contract_matches = self._contract_pattern.findall(user_input)
        
        # 计算各意图的得分
        scores = {
            IntentType.REGULATION_QUERY: len(regulation_matches),
            IntentType.CASE_SEARCH: len(case_matches),
            IntentType.DOCUMENT_DRAFT: len(document_matches),
            IntentType.CONTRACT_REVIEW: len(contract_matches),
        }
        
        # 找出最高分的意图
        max_intent = max(scores, key=scores.get)
        max_score = scores[max_intent]
        
        # 如果没有命中任何关键词，配置了 LLM 时直接走通用回答，避免先识别再回答的双模型调用。
        if max_score == 0:
            if self.llm:
                return IntentResult(
                    intent=IntentType.GENERAL,
                    confidence=0.75,
                    keywords=[],
                )
            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                keywords=[],
            )
        
        # 计算置信度（归一化到0-1）
        # 分数越高置信度越高，但有上限
        confidence = min(0.5 + max_score * 0.1, 0.95)
        
        # 收集命中的关键词
        all_matches = {
            IntentType.REGULATION_QUERY: regulation_matches,
            IntentType.CASE_SEARCH: case_matches,
            IntentType.DOCUMENT_DRAFT: document_matches,
            IntentType.CONTRACT_REVIEW: contract_matches,
        }
        keywords = all_matches[max_intent]
        
        # 置信度低于阈值时，尝试LLM辅助
        if confidence < 0.6 and self.llm:
            return await self._llm_assist_recognize(user_input, scores)
        
        return IntentResult(
            intent=max_intent,
            confidence=confidence,
            keywords=list(set(keywords)),
        )
    
    async def _llm_assist_recognize(
        self,
        user_input: str,
        rule_scores: dict,
    ) -> IntentResult:
        """
        LLM辅助意图识别
        
        当规则匹配置信度较低时，使用LLM进行二次确认
        """
        prompt = f"""分析以下用户输入，判断其意图类型。

用户输入：{user_input}

规则匹配得分：
- 法规查询: {rule_scores.get(IntentType.REGULATION_QUERY, 0)}
- 类案检索: {rule_scores.get(IntentType.CASE_SEARCH, 0)}
- 文书生成: {rule_scores.get(IntentType.DOCUMENT_DRAFT, 0)}
- 合同审查: {rule_scores.get(IntentType.CONTRACT_REVIEW, 0)}

请判断最可能的意图类型，返回JSON格式：
{{"intent": "regulation_query/case_search/document_draft/contract_review/general", "confidence": 0.0-1.0, "reason": "判断理由"}}
"""
        
        try:
            response = await self.llm.call(prompt)
            # 解析LLM响应（简化处理）
            import json
            text = response.strip()
            if "```" in text:
                import re
                fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
                if fenced:
                    text = fenced.group(1).strip()
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end >= start:
                text = text[start:end + 1]
            result = json.loads(text)
            
            return IntentResult(
                intent=IntentType(result["intent"]),
                confidence=result["confidence"],
                keywords=[],
            )
        except Exception:
            # LLM识别失败，返回规则匹配结果
            if all(score == 0 for score in rule_scores.values()):
                return IntentResult(
                    intent=IntentType.GENERAL,
                    confidence=0.6,
                    keywords=[],
                )
            max_intent = max(rule_scores, key=rule_scores.get)
            return IntentResult(
                intent=max_intent,
                confidence=0.5,
                keywords=[],
            )


# ===== 快捷函数 =====

async def quick_recognize(user_input: str, llm_client: Any = None) -> IntentResult:
    """快速意图识别（用于简单场景）"""
    recognizer = IntentRecognizer(llm_client)
    return await recognizer.recognize(user_input)
