"""
External research tool routing tests.
"""

import pytest

from law_agent.sub_agents import ResearchAgent
from law_agent.tools.external_research import ExternalResearchTool


class FakeTavilyClient:
    def __init__(self, fail_search=False):
        self.calls = []
        self.fail_search = fail_search

    async def search_sources(self, **kwargs):
        self.calls.append(("search", kwargs))
        if self.fail_search:
            raise RuntimeError("tavily down")
        return {
            "sources": [
                {
                    "provider": "tavily",
                    "tool": "search",
                    "title": "Tavily source",
                    "url": "https://example.com/a",
                    "snippet": "search snippet",
                    "score": 0.8,
                }
            ],
            "usage": {"credits": 1},
        }

    async def extract_sources(self, **kwargs):
        self.calls.append(("extract", kwargs))
        return {
            "sources": [
                {
                    "provider": "tavily",
                    "tool": "extract",
                    "title": "Extracted source",
                    "url": kwargs["urls"][0],
                    "content": "extracted body",
                }
            ]
        }

    async def map_site(self, **kwargs):
        self.calls.append(("map", kwargs))
        return {
            "sources": [
                {
                    "provider": "tavily",
                    "tool": "map",
                    "title": "Mapped page",
                    "url": "https://example.com/map",
                }
            ]
        }

    async def crawl_site(self, **kwargs):
        self.calls.append(("crawl", kwargs))
        return {
            "sources": [
                {
                    "provider": "tavily",
                    "tool": "crawl",
                    "title": "Crawled page",
                    "url": "https://example.com/crawl",
                    "content": "crawl body",
                }
            ]
        }

    async def research_report(self, **kwargs):
        self.calls.append(("research", kwargs))
        return {
            "answer": "deep report",
            "sources": [
                {
                    "provider": "tavily",
                    "tool": "research",
                    "title": "Research source",
                    "url": "https://example.com/research",
                }
            ],
        }


class FakeBraveClient:
    def __init__(self):
        self.calls = []

    async def llm_context(self, **kwargs):
        self.calls.append(("llm_context", kwargs))
        return {
            "answer": "brave context",
            "sources": [
                {
                    "provider": "brave",
                    "tool": "llm_context",
                    "title": "Brave context source",
                    "url": "https://example.com/context",
                    "snippet": "context snippet",
                }
            ],
        }

    async def web_search(self, **kwargs):
        self.calls.append(("web_search", kwargs))
        return {
            "sources": [
                {
                    "provider": "brave",
                    "tool": "web_search",
                    "title": "Brave web source",
                    "url": "https://example.com/web",
                }
            ]
        }

    async def news_search(self, **kwargs):
        self.calls.append(("news_search", kwargs))
        return {
            "sources": [
                {
                    "provider": "brave",
                    "tool": "news_search",
                    "title": "Brave news source",
                    "url": "https://example.com/news",
                }
            ]
        }

    async def place_search(self, **kwargs):
        self.calls.append(("place_search", kwargs))
        return {
            "sources": [
                {
                    "provider": "brave",
                    "tool": "place_search",
                    "title": "Brave place",
                    "url": "https://example.com/place",
                }
            ]
        }


@pytest.mark.asyncio
async def test_legal_source_check_uses_search_extract_web_and_context():
    tavily = FakeTavilyClient()
    brave = FakeBraveClient()
    tool = ExternalResearchTool(tavily, brave, enabled=True)

    result = await tool.execute("建设工程实际施工人", purpose="legal_source_check")

    assert result.success
    assert [name for name, _ in tavily.calls] == ["search", "extract"]
    assert [name for name, _ in brave.calls] == ["web_search", "llm_context"]
    assert "联网资料仅供检索线索" in result.data["warnings"][0]
    assert {call["tool"] for call in result.data["tool_calls"]} >= {
        "search:general",
        "extract",
        "web_search",
        "llm_context",
    }


@pytest.mark.asyncio
async def test_deep_research_uses_tavily_research_and_brave_context():
    tavily = FakeTavilyClient()
    brave = FakeBraveClient()
    tool = ExternalResearchTool(tavily, brave, enabled=True)

    result = await tool.execute("比较 Tavily 和 Brave", purpose="deep_research")

    assert result.success
    assert [name for name, _ in tavily.calls] == ["research"]
    assert [name for name, _ in brave.calls] == ["llm_context"]
    assert result.data["answer"] == "deep report"


@pytest.mark.asyncio
async def test_site_purposes_use_map_extract_or_crawl():
    tavily = FakeTavilyClient()
    brave = FakeBraveClient()
    tool = ExternalResearchTool(tavily, brave, enabled=True)

    discovery = await tool.execute(
        "司法解释",
        purpose="site_discovery",
        site_url="https://court.gov.cn",
    )
    assert discovery.success
    assert [name for name, _ in tavily.calls] == ["map", "extract"]
    assert [name for name, _ in brave.calls] == ["web_search"]

    tavily.calls.clear()
    brave.calls.clear()
    crawl = await tool.execute(
        "司法解释",
        purpose="site_crawl",
        site_url="https://court.gov.cn",
    )
    assert crawl.success
    assert [name for name, _ in tavily.calls] == ["crawl"]
    assert [name for name, _ in brave.calls] == ["llm_context"]


@pytest.mark.asyncio
async def test_news_and_place_routes_use_dedicated_brave_tools():
    tavily = FakeTavilyClient()
    brave = FakeBraveClient()
    tool = ExternalResearchTool(tavily, brave, enabled=True)

    news = await tool.execute("最新司法政策", purpose="news_check")
    assert news.success
    assert [name for name, _ in brave.calls] == ["news_search", "llm_context"]
    assert tavily.calls[0][1]["topic"] == "news"

    tavily.calls.clear()
    brave.calls.clear()
    place = await tool.execute("深圳中级人民法院", purpose="place_or_entity")
    assert place.success
    assert [name for name, _ in brave.calls] == ["place_search", "web_search"]
    assert [name for name, _ in tavily.calls] == ["search"]


@pytest.mark.asyncio
async def test_provider_failure_degrades_to_remaining_provider():
    tavily = FakeTavilyClient(fail_search=True)
    brave = FakeBraveClient()
    tool = ExternalResearchTool(tavily, brave, enabled=True)

    result = await tool.execute("劳动争议", purpose="quick_search")

    assert result.success
    assert any(call["status"] == "failed" for call in result.data["tool_calls"])
    assert result.data["providers_used"] == ["brave", "tavily"]
    assert any(source["provider"] == "brave" for source in result.data["sources"])


class EmptyRAGClient:
    async def search_regulations(self, **kwargs):
        return []

    async def search_cases(self, **kwargs):
        return []

    async def search_clauses(self, **kwargs):
        return []

    async def get_document_by_id(self, **kwargs):
        return None


class FakeContext:
    def __init__(self):
        self.tools_used = []


@pytest.mark.asyncio
async def test_research_agent_external_fallback_stays_unverified():
    external_tool = ExternalResearchTool(
        FakeTavilyClient(),
        FakeBraveClient(),
        enabled=True,
    )
    agent = ResearchAgent(
        EmptyRAGClient(),
        external_research_tool=external_tool,
    )
    context = FakeContext()

    output = await agent.search_regulations("公司拖欠工资怎么办", context)

    assert "当前本地法规知识库未检索到可引用法规材料" in output
    assert "联网补充资料（需核验）" in output
    assert "## 【依据】" in output
    assert "external.tavily.search:general" in context.tools_used
