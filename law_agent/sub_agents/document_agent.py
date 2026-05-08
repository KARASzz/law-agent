"""
Document子Agent

负责：
1. 文书生成（起诉状、答辩状等）
2. 合同审查
3. 材料检测

注意：这就是一个普通的类，不是独立服务
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..tools.document import DocumentTool, DocumentDraft

if TYPE_CHECKING:
    from ..orchestrator import ProcessingContext


class DocumentAgent:
    """
    文书子Agent
    
    提供文书生成和审查能力
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        初始化Document子Agent
        
        Args:
            llm_client: LLM客户端（可选）
        """
        self.llm = llm_client
        self.document_tool = DocumentTool(llm_client)
    
    async def generate_draft(
        self,
        user_input: str,
        context: ProcessingContext,
        doc_type: str = "民事起诉状",
    ) -> str:
        """
        生成文书初稿
        
        Args:
            user_input: 用户输入
            context: 处理上下文
            doc_type: 文书类型
            
        Returns:
            str: 格式化后的初稿
        """
        # Step 1: 解析用户输入，提取案件信息
        case_info = self._parse_user_input(user_input, doc_type)
        case_info["_raw_user_input"] = user_input
        
        # Step 2: 生成初稿
        result = await self.document_tool.execute(
            doc_type=doc_type,
            case_info=case_info,
        )
        if self.llm:
            generation_mode = (result.metadata or {}).get("generation_mode")
            if generation_mode == "llm":
                context.tools_used.append("llm.generate_document")
            elif generation_mode == "template_fallback":
                context.tools_used.append("llm.generate_document_failed")
        
        if not result.data:
            return f"文书生成失败：{result.error}"
        
        draft = result.data
        
        # Step 3: 格式化输出
        response = self.document_tool.format_results(draft)
        
        # Step 4: 添加确认提示（高风险输出）
        if draft.missing_items:
            response += "\n\n⚠️ **重要提醒**：以上为AI初稿，请在使用前务必人工审阅。"
        
        return response
    
    def _parse_user_input(
        self,
        user_input: str,
        doc_type: str,
    ) -> Dict[str, Any]:
        """
        解析用户输入，提取案件信息
        
        简化实现：直接从用户输入中提取结构化信息
        后续可接入LLM进行更智能的提取
        
        Args:
            user_input: 用户输入
            doc_type: 文书类型
            
        Returns:
            dict: 案件信息
        """
        case_info: Dict[str, Any] = {}
        
        # 简单解析：按行分割，识别字段
        lines = user_input.strip().split("\n")
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测section
            if "原告" in line and ":" not in line:
                current_section = "plaintiff"
                case_info["plaintiff"] = {}
                # 尝试提取名称
                if "：" in line or ":" in line:
                    name = line.split("：")[-1] or line.split(":")[-1]
                    case_info["plaintiff"]["name"] = name.strip()
                continue
            
            if "被告" in line and ":" not in line:
                current_section = "defendant"
                case_info["defendant"] = {}
                if "：" in line or ":" in line:
                    name = line.split("：")[-1] or line.split(":")[-1]
                    case_info["defendant"]["name"] = name.strip()
                continue
            
            if "事实" in line or "理由" in line:
                current_section = "facts"
                case_info["facts"] = ""
                if "：" in line or ":" in line:
                    case_info["facts"] = line.split("：")[-1] or line.split(":")[-1]
                continue
            
            if "请求" in line or "诉求" in line:
                current_section = "claims"
                case_info["claims"] = []
                if "：" in line or ":" in line:
                    claim = line.split("：")[-1] or line.split(":")[-1]
                    case_info["claims"].append(claim.strip())
                continue
            
            # 处理字段值
            if "：" in line or ":" in line:
                key, value = line.split("：", 1) if "：" in line else line.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                if current_section == "plaintiff":
                    case_info["plaintiff"][key] = value
                elif current_section == "defendant":
                    case_info["defendant"][key] = value
                elif current_section == "facts":
                    case_info["facts"] += " " + value
                elif current_section == "claims":
                    case_info["claims"].append(value)
                elif key == "管辖法院":
                    case_info["jurisdiction"] = value
        
        return case_info
    
    async def review_contract(
        self,
        contract_text: str,
        context: ProcessingContext,
        review_type: str = "risk",
    ) -> str:
        """
        审查合同
        
        Args:
            contract_text: 合同文本
            context: 处理上下文
            review_type: 审查类型（risk/compliance/clause）
            
        Returns:
            str: 审查结果
        """
        # TODO: 实现合同审查逻辑
        # 简化实现：
        return f"""
## 合同审查结果

### 基本信息
- 合同长度：{len(contract_text)} 字符
- 审查类型：{review_type}

### 风险提示
⚠️ 合同审查需要更详细的信息，请提供：
1. 合同类型（如：买卖合同、租赁合同、劳动合同等）
2. 具体需要审查的条款

### 建议
请详细描述您的审查需求，我将为您提供更有针对性的建议。

---
⚠️ 本审查意见仅供参考，不构成正式法律意见。
"""
    
    async def check_missing_items(
        self,
        doc_type: str,
        case_info: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """
        检查缺失的材料
        
        Args:
            doc_type: 文书类型
            case_info: 案件信息
            
        Returns:
            dict: 缺失材料列表
        """
        result = await self.document_tool.execute(doc_type, case_info)
        
        if result.data:
            return {
                "missing": result.data.missing_items,
                "suggestions": result.data.suggestions,
            }
        
        return {"missing": [], "suggestions": []}


# ===== 便捷函数 =====

async def quick_generate_draft(
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
    agent = DocumentAgent(llm_client)
    
    result = await agent.document_tool.execute(doc_type, case_info)
    
    if result.success or result.data:
        return result.data
    
    return None
