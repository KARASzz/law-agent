"""
OpenAI-compatible LLM client.

用于接入支持 /chat/completions 的模型服务。代码层只负责调用和解析，
风控、审阅、导出/发送门禁仍由 Law Agent 后端控制。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class LLMResponse:
    """LLM 调用结果。"""

    content: str
    raw: Dict[str, Any]
    model: str


class OpenAICompatibleLLMClient:
    """OpenAI 兼容模式 LLM 客户端。"""

    def __init__(
        self,
        api_endpoint: str,
        api_key: str,
        model: str,
        fallback_models: Optional[List[str]] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: int = 60,
    ):
        self.api_endpoint = api_endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.fallback_models = [
            fallback_model
            for fallback_model in (fallback_models or [])
            if fallback_model and fallback_model != model
        ]
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """用单轮 prompt 调用模型，返回文本。"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """调用 /chat/completions。"""
        url = f"{self.api_endpoint}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        models = [self.model, *self.fallback_models]
        last_error: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for model in models:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": self.temperature if temperature is None else temperature,
                    "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
                    "stream": False,
                }
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    content = self._extract_content(data)
                    if content.strip():
                        return LLMResponse(content=content, raw=data, model=model)
                    last_error = ValueError(f"empty LLM response from model {model}")
                except Exception as exc:
                    last_error = exc

        if last_error:
            raise last_error
        raise ValueError("no LLM model configured")

    def _extract_content(self, data: Dict[str, Any]) -> str:
        """兼容 OpenAI 风格响应，提取首个候选文本。"""
        choices = data.get("choices") or []
        if not choices:
            return ""

        first = choices[0]
        message = first.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content

        text = first.get("text")
        if isinstance(text, str):
            return text

        return ""


def create_llm_client(config: Any) -> Optional[OpenAICompatibleLLMClient]:
    """按配置创建 LLM 客户端。未配置 key 时返回 None。"""
    if not getattr(config, "api_key", ""):
        return None

    provider = getattr(config, "provider", "openai-compatible")
    if provider not in {"openai", "openai-compatible", "custom"}:
        return None

    return OpenAICompatibleLLMClient(
        api_endpoint=config.api_endpoint,
        api_key=config.api_key,
        model=config.model,
        fallback_models=getattr(config, "fallback_models", []),
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout=getattr(config, "timeout", 60),
    )
