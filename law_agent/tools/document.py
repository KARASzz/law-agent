"""
文书生成工具

提供文书初稿生成能力，包括：
1. 起诉状生成
2. 答辩状生成
3. 申请书生成
4. 缺失材料检测
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
import re

from .base import BaseTool, ToolResult, ToolType


@dataclass
class CaseInfo:
    """案件信息"""
    plaintiff: Dict[str, str] = field(default_factory=dict)  # 原告信息
    defendant: Dict[str, str] = field(default_factory=dict)  # 被告信息
    third_party: Dict[str, str] = None  # 第三人（可选）
    facts: str = ""  # 事实与理由
    claims: List[str] = field(default_factory=list)  # 诉讼请求
    evidence: List[Dict[str, str]] = field(default_factory=list)  # 证据
    case_type: str = "民事"  # 案件类型
    claim_amount: Optional[float] = None  # 诉讼金额
    raw_user_input: str = ""  # 原始脱敏输入
    
    def to_dict(self) -> dict:
        return {
            "plaintiff": self.plaintiff,
            "defendant": self.defendant,
            "third_party": self.third_party,
            "facts": self.facts,
            "claims": self.claims,
            "evidence": self.evidence,
            "case_type": self.case_type,
            "claim_amount": self.claim_amount,
            "raw_user_input": self.raw_user_input,
        }


@dataclass
class DocumentDraft:
    """文书初稿"""
    doc_type: str  # 文书类型
    title: str  # 文书标题
    content: str  # 文书内容
    missing_items: List[str] = field(default_factory=list)  # 缺失材料
    suggestions: List[str] = field(default_factory=list)  # 建议
    legal_basis: List[Dict[str, str]] = field(default_factory=list)  # 法律依据


class DocumentTool(BaseTool):
    """
    文书生成工具
    
    提供：
    1. 起诉状生成
    2. 答辩状生成
    3. 申请书生成
    4. 缺失材料检测
    """
    
    name = "generate_document"
    description = "根据案件信息生成法律文书初稿"
    tool_type = ToolType.DOCUMENT
    
    # 支持的文书类型
    SUPPORTED_TYPES = [
        "民事起诉状",
        "答辩状",
        "上诉状",
        "申请书",
        "律师函",
    ]
    
    # 最小必要字段
    REQUIRED_FIELDS = {
        "民事起诉状": ["plaintiff.name", "defendant.name", "facts", "claims"],
        "答辩状": ["defendant.name", "plaintiff.name"],
        "上诉状": ["appellant.name", "original_judgment"],
        "申请书": ["applicant.name", "application_reason"],
    }
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        初始化文书生成工具
        
        Args:
            llm_client: LLM客户端
        """
        self.llm = llm_client
    
    async def execute(
        self,
        doc_type: str,
        case_info: Dict[str, Any],
        template: Optional[str] = None,
    ) -> ToolResult:
        """
        执行文书生成
        
        Args:
            doc_type: 文书类型
            case_info: 案件信息
            template: 模板名称（可选）
            
        Returns:
            ToolResult: 生成结果
        """
        try:
            # 解析案件信息
            parsed_info = self._parse_case_info(case_info)
            
            # 检查缺失字段
            missing_items = self._check_missing_fields(doc_type, parsed_info)
            
            # 生成初稿
            if self.llm:
                draft = await self._generate_with_llm(doc_type, parsed_info, template)
            else:
                draft = self._generate_from_template(doc_type, parsed_info, template)
            
            # 提取法律依据
            legal_basis = await self._extract_legal_basis(draft)
            
            # 组装结果
            document_draft = DocumentDraft(
                doc_type=doc_type,
                title=draft.get("title", self._get_title(doc_type)),
                content=draft.get("content", ""),
                missing_items=missing_items,
                suggestions=self._generate_suggestions(missing_items),
                legal_basis=legal_basis,
            )
            
            return ToolResult(
                success=len(missing_items) == 0,  # 有缺失材料但不失败
                data=document_draft,
                metadata={
                    "doc_type": doc_type,
                    "has_missing": len(missing_items) > 0,
                    "missing_count": len(missing_items),
                    "generation_mode": draft.get("_generation_mode", "template"),
                    "llm_error": draft.get("_llm_error"),
                },
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"文书生成失败: {str(e)}",
            )
    
    def _parse_case_info(self, case_info: Dict[str, Any]) -> CaseInfo:
        """解析案件信息"""
        info = CaseInfo()
        
        # 解析原告
        if "plaintiff" in case_info:
            info.plaintiff = case_info["plaintiff"]
        
        # 解析被告
        if "defendant" in case_info:
            info.defendant = case_info["defendant"]
        
        # 解析第三人
        if "third_party" in case_info:
            info.third_party = case_info["third_party"]
        
        # 解析事实
        if "facts" in case_info:
            info.facts = case_info["facts"]
        
        # 解析诉讼请求
        if "claims" in case_info:
            claims = case_info["claims"]
            if isinstance(claims, str):
                info.claims = [c.strip() for c in claims.split("\n") if c.strip()]
            elif isinstance(claims, list):
                info.claims = claims
        
        # 解析证据
        if "evidence" in case_info:
            info.evidence = case_info["evidence"]
        
        # 解析案件类型
        if "case_type" in case_info:
            info.case_type = case_info["case_type"]
        
        # 解析诉讼金额
        if "claim_amount" in case_info:
            info.claim_amount = case_info["claim_amount"]

        if "_raw_user_input" in case_info:
            info.raw_user_input = case_info["_raw_user_input"]
        
        return info
    
    def _check_missing_fields(self, doc_type: str, info: CaseInfo) -> List[str]:
        """检查缺失的必要字段"""
        required = self.REQUIRED_FIELDS.get(doc_type, [])
        missing = []
        
        for field_path in required:
            parts = field_path.split(".")
            
            if parts[0] == "plaintiff":
                if not info.plaintiff.get("name"):
                    missing.append("原告姓名/名称")
            elif parts[0] == "defendant":
                if not info.defendant.get("name"):
                    missing.append("被告姓名/名称")
            elif parts[0] == "facts" and not info.facts:
                missing.append("事实与理由")
            elif parts[0] == "claims" and not info.claims:
                missing.append("诉讼请求")
        
        return missing
    
    async def _generate_with_llm(
        self,
        doc_type: str,
        info: CaseInfo,
        template: Optional[str] = None,
    ) -> Dict[str, str]:
        """使用LLM生成文书"""
        template_draft = self._generate_from_template(doc_type, info, template)
        prompt = f"""
请根据以下脱敏案件信息生成一份{doc_type}初稿。

要求：
1. 只依据输入信息生成，不得编造当事人身份、金额、法院、案号或证据。
2. 缺失信息必须保留【待补充】占位。
3. 语气应正式、审慎，适合作为律师内部初稿。
4. 不要输出免责声明，系统会统一追加。
5. 只返回 JSON，不要返回 Markdown 代码块。

返回格式：
{{
  "title": "{doc_type}",
  "content": "完整文书正文"
}}

案件信息 JSON：
{json.dumps(info.to_dict(), ensure_ascii=False)}

模板参考：
{template_draft.get("content", "")}
"""
        try:
            response = await self.llm.call(
                prompt,
                system_prompt=(
                    "你是中国法律文书起草助手，只生成内部审阅初稿。"
                    "不得虚构事实，不得给出未经确认的最终法律意见。"
                ),
                temperature=0.2,
            )
            parsed = self._parse_llm_json(response)
            title = parsed.get("title") or self._get_title(doc_type)
            content = parsed.get("content") or ""
            if content.strip():
                return {
                    "title": title,
                    "content": content.strip(),
                    "_generation_mode": "llm",
                }
        except Exception as exc:
            template_draft["_llm_error"] = type(exc).__name__

        template_draft["_generation_mode"] = "template_fallback"
        return template_draft

    def _parse_llm_json(self, response: str) -> Dict[str, str]:
        """解析模型返回的 JSON，兼容被 Markdown 包裹的情况。"""
        text = response.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end >= start:
            text = text[start:end + 1]

        data = json.loads(text)
        if not isinstance(data, dict):
            return {}
        return data
    
    def _generate_from_template(
        self,
        doc_type: str,
        info: CaseInfo,
        template: Optional[str] = None,
    ) -> Dict[str, str]:
        """使用模板生成文书"""
        
        if doc_type == "民事起诉状":
            return self._generate_complaint(info)
        elif doc_type == "答辩状":
            return self._generate_defense(info)
        else:
            return {"title": self._get_title(doc_type), "content": "暂不支持该文书类型"}
    
    def _generate_complaint(self, info: CaseInfo) -> Dict[str, str]:
        """生成民事起诉状"""
        
        # 原告信息
        plaintiff = info.plaintiff
        plaintiff_text = f"{plaintiff.get('name', '【原告姓名/名称】')}"
        if plaintiff.get('identity'):
            plaintiff_text += f"\n    身份证号/统一社会信用代码：{plaintiff.get('identity')}"
        if plaintiff.get('address'):
            plaintiff_text += f"\n    地址：{plaintiff.get('address')}"
        if plaintiff.get('phone'):
            plaintiff_text += f"\n    电话：{plaintiff.get('phone')}"
        
        # 被告信息
        defendant = info.defendant
        defendant_text = f"{defendant.get('name', '【被告姓名/名称】')}"
        if defendant.get('identity'):
            defendant_text += f"\n    身份证号/统一社会信用代码：{defendant.get('identity')}"
        if defendant.get('address'):
            defendant_text += f"\n    地址：{defendant.get('address')}"
        if defendant.get('phone'):
            defendant_text += f"\n    电话：{defendant.get('phone')}"
        
        # 诉讼请求
        claims_text = ""
        if info.claims:
            for i, claim in enumerate(info.claims, 1):
                claims_text += f"{i}. {claim}\n"
        else:
            claims_text = "【请填写诉讼请求】\n"
        
        # 事实与理由
        facts_text = info.facts if info.facts else "【请填写事实与理由】"
        
        # 证据
        evidence_text = ""
        if info.evidence:
            for i, ev in enumerate(info.evidence, 1):
                evidence_text += f"{i}. {ev.get('name', '证据名称')}（{ev.get('type', '证据类型')}）"
                if ev.get('证明内容'):
                    evidence_text += f" - 证明：{ev.get('证明内容')}"
                evidence_text += "\n"
        else:
            evidence_text = "【如有证据，请列出】\n"
        
        content = f"""
民事起诉状

原告：{plaintiff_text}

被告：{defendant_text}

诉讼请求：
{claims_text}

事实与理由：
{facts_text}

证据：
{evidence_text}

此致
{plaintiff.get('jurisdiction', '【管辖法院】')}人民法院

                        原告（签名/盖章）：_______________
                        
                        日期：_______年____月____日
"""
        
        return {
            "title": "民事起诉状",
            "content": content.strip(),
        }
    
    def _generate_defense(self, info: CaseInfo) -> Dict[str, str]:
        """生成答辩状"""
        
        content = f"""
答辩状

答辩人：{info.defendant.get('name', '【被告姓名/名称】')}
        地址：{info.defendant.get('address', '【被告地址】')}
        电话：{info.defendant.get('phone', '【被告电话】')}

针对原告：{info.plaintiff.get('name', '【原告姓名/名称】')}的起诉，答辩人答辩如下：

【请在此填写答辩意见】

综上所述，答辩人认为：

1. 【答辩要点1】
2. 【答辩要点2】

此致
【管辖法院】人民法院

                        答辩人（签名/盖章）：_______________
                        
                        日期：_______年____月____日
"""
        
        return {
            "title": "答辩状",
            "content": content.strip(),
        }
    
    def _get_title(self, doc_type: str) -> str:
        """获取文书标题"""
        titles = {
            "民事起诉状": "民事起诉状",
            "答辩状": "答辩状",
            "上诉状": "民事上诉状",
            "申请书": "申请书",
            "律师函": "律师函",
        }
        return titles.get(doc_type, doc_type)
    
    async def _extract_legal_basis(self, draft: Dict[str, str]) -> List[Dict[str, str]]:
        """提取法律依据"""
        # TODO: 实现法律依据提取
        return []
    
    def _generate_suggestions(self, missing_items: List[str]) -> List[str]:
        """生成补充建议"""
        suggestions = []
        
        if missing_items:
            suggestions.append(f"请补充以下信息：{', '.join(missing_items)}")
        
        if "诉讼请求" in missing_items:
            suggestions.append("建议明确诉讼请求的金额或具体内容")
        
        if "事实与理由" in missing_items:
            suggestions.append("建议详细描述纠纷发生的时间、地点、经过等要素")
        
        return suggestions
    
    def format_results(self, draft: DocumentDraft) -> str:
        """
        格式化文书初稿
        
        Args:
            draft: 文书初稿
            
        Returns:
            str: 格式化文本
        """
        text = f"# {draft.title}\n\n"
        text += draft.content
        
        if draft.missing_items:
            text += "\n\n---\n\n## ⚠️ 待补材料\n\n"
            for item in draft.missing_items:
                text += f"- {item}\n"
        
        if draft.suggestions:
            text += "\n## 💡 建议\n\n"
            for suggestion in draft.suggestions:
                text += f"- {suggestion}\n"
        
        text += "\n\n---\n\n"
        text += "⚠️ **免责声明**：以上为AI生成的初稿，请在使用前务必人工审阅并修改。\n"
        text += "高风险文书建议咨询执业律师。\n"
        
        return text.strip()


# ===== 便捷函数 =====

async def generate_document(
    doc_type: str,
    case_info: Dict[str, Any],
    llm_client: Optional[Any] = None,
) -> Optional[DocumentDraft]:
    """
    快速生成文书
    
    Args:
        doc_type: 文书类型
        case_info: 案件信息
        llm_client: LLM客户端
        
    Returns:
        DocumentDraft: 文书初稿
    """
    tool = DocumentTool(llm_client)
    result = await tool.execute(doc_type, case_info)
    
    if result.success or result.data:
        return result.data
    return None
