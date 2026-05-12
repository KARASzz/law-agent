"""
配置模块

提供应用配置管理
"""

from typing import List, Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    orchestration_db_path: str = "data/orchestration.db"


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


class RawEnvSettings(BaseSettings):
    """扁平环境变量入口，兼容现有 .env 命名。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    RAG_API_ENDPOINT: str = "http://localhost:8000"
    RAG_API_KEY: str = ""
    RAG_TIMEOUT: int = 30

    LLM_PROVIDER: str = "openai-compatible"
    MINIMAX_API_ENDPOINT: str = "https://api.minimaxi.com/v1"
    MINIMAX_API_KEY: str = ""
    MINIMAX_MODEL: str = "MiniMax-M2.7"
    MINIMAX_FALLBACK_MODELS: str = ""
    DASHSCOPE_API_ENDPOINT: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_MODEL: str = "qwen-plus"
    DASHSCOPE_FALLBACK_MODELS: str = ""
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT: int = 60

    AUDIT_DB_PATH: str = "data/audit.db"
    TASK_DB_PATH: str = "data/tasks.db"
    CLIENT_PROFILE_DB_PATH: str = "data/client_profiles.db"
    ORCHESTRATION_DB_PATH: str = "data/orchestration.db"

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    SERVER_DEBUG: bool = False
    ENVIRONMENT: str = "development"

    ENABLE_EXTERNAL_SEARCH: bool = False
    TAVILY_API_KEY: str = ""
    TAVILY_PROJECT_ID: str = ""
    BRAVE_SEARCH_API_KEY: str = ""
    WEB_SEARCH_TIMEOUT: int = 20
    WEB_SEARCH_MAX_RESULTS: int = 5
    WEB_SEARCH_MAX_TOKENS: int = 8192


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

    raw = RawEnvSettings()
    config = AppConfig()
    
    config.rag.api_endpoint = raw.RAG_API_ENDPOINT
    config.rag.api_key = raw.RAG_API_KEY
    config.rag.timeout = raw.RAG_TIMEOUT
    
    config.llm.provider = raw.LLM_PROVIDER
    if raw.LLM_PROVIDER == "dashscope":
        config.llm.api_endpoint = raw.DASHSCOPE_API_ENDPOINT
        config.llm.api_key = raw.DASHSCOPE_API_KEY
        config.llm.model = raw.DASHSCOPE_MODEL
        fallback_models = raw.DASHSCOPE_FALLBACK_MODELS
    else:
        config.llm.api_endpoint = raw.MINIMAX_API_ENDPOINT
        config.llm.api_key = raw.MINIMAX_API_KEY
        config.llm.model = raw.MINIMAX_MODEL
        fallback_models = raw.MINIMAX_FALLBACK_MODELS
    config.llm.fallback_models = [
        model.strip()
        for model in fallback_models.split(",")
        if model.strip()
    ]
    config.llm.temperature = raw.LLM_TEMPERATURE
    config.llm.max_tokens = raw.LLM_MAX_TOKENS
    config.llm.timeout = raw.LLM_TIMEOUT
    
    config.environment = raw.ENVIRONMENT
    config.database.audit_db_path = raw.AUDIT_DB_PATH
    config.database.task_db_path = raw.TASK_DB_PATH
    config.database.client_profile_db_path = raw.CLIENT_PROFILE_DB_PATH
    config.database.orchestration_db_path = raw.ORCHESTRATION_DB_PATH

    config.server.host = raw.SERVER_HOST
    config.server.port = raw.SERVER_PORT
    config.server.debug = raw.SERVER_DEBUG

    config.external_search.enabled = raw.ENABLE_EXTERNAL_SEARCH
    config.external_search.tavily_api_key = raw.TAVILY_API_KEY
    config.external_search.tavily_project_id = raw.TAVILY_PROJECT_ID
    config.external_search.brave_search_api_key = raw.BRAVE_SEARCH_API_KEY
    config.external_search.timeout = raw.WEB_SEARCH_TIMEOUT
    config.external_search.max_results = raw.WEB_SEARCH_MAX_RESULTS
    config.external_search.max_tokens = raw.WEB_SEARCH_MAX_TOKENS
    
    return config


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取配置实例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
