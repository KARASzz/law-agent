"""
LLM client and LLM-assisted generation tests.
"""

import json

import pytest
import httpx

from law_agent.llm import OpenAICompatibleLLMClient
from law_agent.tools.document import DocumentTool


def test_openai_compatible_llm_extracts_message_content():
    client = OpenAICompatibleLLMClient(
        api_endpoint="https://example.com/v1",
        api_key="test",
        model="primary-model",
    )

    content = client._extract_content(
        {"choices": [{"message": {"content": "模型输出"}}]}
    )

    assert content == "模型输出"


@pytest.mark.asyncio
async def test_openai_compatible_llm_falls_back_to_next_model(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            calls.append(json["model"])
            request = httpx.Request("POST", url)
            if json["model"] == "primary-model":
                return httpx.Response(429, json={"error": "busy"}, request=request)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "回退模型成功"}}]},
                request=request,
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = OpenAICompatibleLLMClient(
        api_endpoint="https://example.com/v1",
        api_key="test",
        model="primary-model",
        fallback_models=["fallback-model"],
    )

    response = await client.chat([{"role": "user", "content": "test"}])

    assert response.content == "回退模型成功"
    assert response.model == "fallback-model"
    assert calls == ["primary-model", "fallback-model"]


@pytest.mark.asyncio
async def test_document_tool_uses_llm_json_content():
    class FakeLLM:
        async def call(self, prompt, **kwargs):
            return json.dumps(
                {
                    "title": "民事起诉状",
                    "content": "这是模型生成的起诉状初稿。",
                },
                ensure_ascii=False,
            )

    tool = DocumentTool(FakeLLM())
    result = await tool.execute(
        doc_type="民事起诉状",
        case_info={
            "plaintiff": {"name": "张三"},
            "defendant": {"name": "李四"},
            "facts": "双方存在借款纠纷。",
            "claims": ["请求返还借款。"],
        },
    )

    assert result.data.title == "民事起诉状"
    assert result.data.content == "这是模型生成的起诉状初稿。"
    assert result.success is True
    assert result.metadata["generation_mode"] == "llm"


@pytest.mark.asyncio
async def test_document_tool_falls_back_when_llm_fails():
    class FailingLLM:
        async def call(self, prompt, **kwargs):
            raise RuntimeError("quota exceeded")

    tool = DocumentTool(FailingLLM())
    result = await tool.execute(
        doc_type="民事起诉状",
        case_info={
            "plaintiff": {"name": "张三"},
            "defendant": {"name": "李四"},
            "facts": "双方存在借款纠纷。",
            "claims": ["请求返还借款。"],
        },
    )

    assert "民事起诉状" in result.data.content
    assert result.metadata["generation_mode"] == "template_fallback"
    assert result.metadata["llm_error"] == "RuntimeError"
