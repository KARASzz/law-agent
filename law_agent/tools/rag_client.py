"""
RAG库客户端

对接阿里云RAG库，提供检索能力
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import httpx
import json


@dataclass
class RAGDocument:
    """RAG检索结果文档"""
    id: str
    title: str
    content: str
    source: str
    source_type: str  # law, interpretation, case, etc.
    effective_date: Optional[str] = None
    expire_date: Optional[str] = None
    jurisdiction: Optional[str] = None  # 全国, 北京, 上海, etc.
    authority_level: Optional[str] = None  # 法律, 行政法规, 司法解释, etc.
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "source_type": self.source_type,
            "effective_date": self.effective_date,
            "expire_date": self.expire_date,
            "jurisdiction": self.jurisdiction,
            "authority_level": self.authority_level,
            "relevance_score": self.relevance_score,
            "metadata": self.metadata,
        }


class RAGClient:
    """
    阿里云RAG库客户端
    
    提供：
    1. 法规检索
    2. 类案检索
    3. 条款检索
    """
    
    def __init__(
        self,
        api_endpoint: str,
        api_key: str,
        timeout: int = 30,
    ):
        """
        初始化RAG客户端
        
        Args:
            api_endpoint: API端点
            api_key: API密钥
            timeout: 超时时间（秒）
        """
        self.api_endpoint = api_endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        """关闭客户端"""
        await self._client.aclose()
    
    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict] = None,
    ) -> dict:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法
            path: 请求路径
            data: 请求数据
            
        Returns:
            dict: 响应数据
        """
        url = f"{self.api_endpoint}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        response = await self._client.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
        )
        
        response.raise_for_status()
        return response.json()
    
    async def search_regulations(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        authority_level: Optional[str] = None,
        effective_only: bool = True,
        top_k: int = 5,
    ) -> List[RAGDocument]:
        """
        检索法规
        
        Args:
            query: 检索query
            jurisdiction: 法域（可选）
            authority_level: 权威等级（可选）
            effective_only: 仅返回有效法规
            top_k: 返回数量
            
        Returns:
            List[RAGDocument]: 检索结果
        """
        data = {
            "query": query,
            "top_k": top_k,
            "filters": {},
        }
        
        if jurisdiction:
            data["filters"]["jurisdiction"] = jurisdiction
        
        if authority_level:
            data["filters"]["authority_level"] = authority_level
        
        if effective_only:
            data["filters"]["effective_only"] = True
        
        try:
            response = await self._request("POST", "/v1/regulations/search", data)
            return [
                RAGDocument(**doc) for doc in response.get("results", [])
            ]
        except Exception as e:
            # TODO: 实现降级策略
            print(f"RAG search failed: {e}")
            return []
    
    async def search_cases(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        court_level: Optional[str] = None,
        case_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RAGDocument]:
        """
        检索案例
        
        Args:
            query: 检索query
            jurisdiction: 地域（可选）
            court_level: 法院层级（可选）
            case_type: 案例类型（可选）
            top_k: 返回数量
            
        Returns:
            List[RAGDocument]: 检索结果
        """
        data = {
            "query": query,
            "top_k": top_k,
            "filters": {},
        }
        
        if jurisdiction:
            data["filters"]["jurisdiction"] = jurisdiction
        
        if court_level:
            data["filters"]["court_level"] = court_level
        
        if case_type:
            data["filters"]["case_type"] = case_type
        
        try:
            response = await self._request("POST", "/v1/cases/search", data)
            return [
                RAGDocument(**doc) for doc in response.get("results", [])
            ]
        except Exception as e:
            print(f"RAG case search failed: {e}")
            return []
    
    async def search_clauses(
        self,
        query: str,
        clause_type: Optional[str] = None,
        contract_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RAGDocument]:
        """
        检索合同条款
        
        Args:
            query: 检索query
            clause_type: 条款类型（可选）
            contract_type: 合同类型（可选）
            top_k: 返回数量
            
        Returns:
            List[RAGDocument]: 检索结果
        """
        data = {
            "query": query,
            "top_k": top_k,
            "filters": {},
        }
        
        if clause_type:
            data["filters"]["clause_type"] = clause_type
        
        if contract_type:
            data["filters"]["contract_type"] = contract_type
        
        try:
            response = await self._request("POST", "/v1/clauses/search", data)
            return [
                RAGDocument(**doc) for doc in response.get("results", [])
            ]
        except Exception as e:
            print(f"RAG clause search failed: {e}")
            return []
    
    async def get_document_by_id(self, doc_id: str) -> Optional[RAGDocument]:
        """
        根据ID获取文档详情
        
        Args:
            doc_id: 文档ID
            
        Returns:
            RAGDocument: 文档详情
        """
        try:
            response = await self._request("GET", f"/v1/documents/{doc_id}")
            return RAGDocument(**response)
        except Exception as e:
            print(f"RAG get document failed: {e}")
            return None
    
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            bool: 是否健康
        """
        try:
            response = await self._request("GET", "/health")
            return response.get("status") == "ok"
        except Exception:
            return False


# ===== 环境变量配置 =====

import os

def create_rag_client_from_env() -> RAGClient:
    """
    从环境变量创建RAG客户端
    
    环境变量：
    - RAG_API_ENDPOINT: API端点
    - RAG_API_KEY: API密钥
    - RAG_TIMEOUT: 超时时间（秒）
    """
    endpoint = os.getenv("RAG_API_ENDPOINT", "http://localhost:8000")
    api_key = os.getenv("RAG_API_KEY", "")
    timeout = int(os.getenv("RAG_TIMEOUT", "30"))
    
    return RAGClient(endpoint, api_key, timeout)
