"""
Configuration loading tests.
"""

from config import settings


def test_llm_config_uses_minimax_env_and_ignores_frozen_llm_env(monkeypatch):
    monkeypatch.setattr(settings, "load_dotenv", lambda: None)

    monkeypatch.setenv("LLM_API_ENDPOINT", "https://legacy.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "legacy-key")
    monkeypatch.setenv("LLM_MODEL", "legacy-model")
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "legacy-fallback")

    monkeypatch.setenv("MINIMAX_API_ENDPOINT", "https://api.minimaxi.com/v1")
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-key")
    monkeypatch.setenv("MINIMAX_MODEL", "MiniMax-M2.7")
    monkeypatch.setenv("MINIMAX_FALLBACK_MODELS", "")

    config = settings.load_config()

    assert config.llm.api_endpoint == "https://api.minimaxi.com/v1"
    assert config.llm.api_key == "minimax-key"
    assert config.llm.model == "MiniMax-M2.7"
    assert config.llm.fallback_models == []


def test_llm_config_defaults_to_minimax_without_key(monkeypatch):
    monkeypatch.setattr(settings, "load_dotenv", lambda: None)

    for name in (
        "LLM_API_ENDPOINT",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_FALLBACK_MODELS",
        "MINIMAX_API_ENDPOINT",
        "MINIMAX_API_KEY",
        "MINIMAX_MODEL",
        "MINIMAX_FALLBACK_MODELS",
    ):
        monkeypatch.delenv(name, raising=False)

    config = settings.load_config()

    assert config.llm.api_endpoint == "https://api.minimaxi.com/v1"
    assert config.llm.api_key == ""
    assert config.llm.model == "MiniMax-M2.7"
    assert config.llm.fallback_models == []
