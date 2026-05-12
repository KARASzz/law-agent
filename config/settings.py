"""
配置模块

提供应用配置管理
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv 是可选运行依赖
    load_dotenv = None


class RAGConfig(BaseModel):
    """RAG库配置"""
    api_endpoint: str = "http://localhost:8000"
    api_key: str = ""
    timeout: int = 30


class LLMConfig(BaseModel):
    """LLM配置"""
    provider: str = "openai-compatible"  # openai-compatible / openai / custom
    api_endpoint: str = "https://api.minimaxi.com/v1"
    api_key: str = ""
    model: str = "MiniMax-M2.7"
    fallback_models: List[str] = []
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 60


class DatabaseConfig(BaseModel):
    """数据库配置"""
    audit_db_path: str = "data/audit.db"
    task_db_path: str = "data/tasks.db"
    client_profile_db_path: str = "data/client_profiles.db"


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class ExternalSearchConfig(BaseModel):
    """联网研究工具配置"""
    enabled: bool = False
    tavily_api_key: str = ""
    tavily_project_id: str = ""
    brave_search_api_key: str = ""
    timeout: int = 20
    max_results: int = 5
    max_tokens: int = 8192


class AppConfig(BaseModel):
    """应用配置"""
    app_name: str = "律师智能体"
    version: str = "0.1.0"
    environment: str = "development"  # development / production
    
    # 子配置
    rag: RAGConfig = RAGConfig()
    llm: LLMConfig = LLMConfig()
    database: DatabaseConfig = DatabaseConfig()
    server: ServerConfig = ServerConfig()
    external_search: ExternalSearchConfig = ExternalSearchConfig()
    
    # 功能开关
    enable_citation_verify: bool = True
    enable_risk_label: bool = True
    enable_audit: bool = True
    
    # 性能配置
    max_concurrent_tasks: int = 10
    task_timeout: int = 60


def load_config() -> AppConfig:
    """
    加载配置
    
    优先级：
    1. 环境变量
    2. .env文件
    3. 默认值
    """
    if load_dotenv:
        load_dotenv()

    config = AppConfig()
    
    # 从环境变量加载
    config.rag.api_endpoint = os.getenv("RAG_API_ENDPOINT", config.rag.api_endpoint)
    config.rag.api_key = os.getenv("RAG_API_KEY", config.rag.api_key)
    
    config.llm.provider = os.getenv("LLM_PROVIDER", config.llm.provider)
    config.llm.api_endpoint = os.getenv("MINIMAX_API_ENDPOINT", config.llm.api_endpoint)
    config.llm.api_key = os.getenv("MINIMAX_API_KEY", config.llm.api_key)
    config.llm.model = os.getenv("MINIMAX_MODEL", config.llm.model)
    fallback_models = os.getenv("MINIMAX_FALLBACK_MODELS", "")
    config.llm.fallback_models = [
        model.strip()
        for model in fallback_models.split(",")
        if model.strip()
    ]
    config.llm.temperature = float(os.getenv("LLM_TEMPERATURE", config.llm.temperature))
    config.llm.max_tokens = int(os.getenv("LLM_MAX_TOKENS", config.llm.max_tokens))
    config.llm.timeout = int(os.getenv("LLM_TIMEOUT", config.llm.timeout))
    
    config.environment = os.getenv("ENVIRONMENT", config.environment)
    config.database.audit_db_path = os.getenv("AUDIT_DB_PATH", config.database.audit_db_path)
    config.database.task_db_path = os.getenv("TASK_DB_PATH", config.database.task_db_path)
    config.database.client_profile_db_path = os.getenv(
        "CLIENT_PROFILE_DB_PATH",
        config.database.client_profile_db_path,
    )
    config.external_search.enabled = _env_bool(
        "ENABLE_EXTERNAL_SEARCH",
        config.external_search.enabled,
    )
    config.external_search.tavily_api_key = os.getenv(
        "TAVILY_API_KEY",
        config.external_search.tavily_api_key,
    )
    config.external_search.tavily_project_id = os.getenv(
        "TAVILY_PROJECT_ID",
        config.external_search.tavily_project_id,
    )
    config.external_search.brave_search_api_key = os.getenv(
        "BRAVE_SEARCH_API_KEY",
        config.external_search.brave_search_api_key,
    )
    config.external_search.timeout = int(os.getenv(
        "WEB_SEARCH_TIMEOUT",
        config.external_search.timeout,
    ))
    config.external_search.max_results = int(os.getenv(
        "WEB_SEARCH_MAX_RESULTS",
        config.external_search.max_results,
    ))
    config.external_search.max_tokens = int(os.getenv(
        "WEB_SEARCH_MAX_TOKENS",
        config.external_search.max_tokens,
    ))
    
    return config


def _env_bool(name: str, default: bool) -> bool:
    """读取常见布尔环境变量写法。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取配置实例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
