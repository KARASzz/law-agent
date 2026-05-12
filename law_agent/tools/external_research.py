"""
联网研究工具组。

Tavily 和 Brave 在这里被封装成后端工具，不依赖 MCP 客户端运行时。
调用方只面对 ExternalResearchTool，由它按 purpose 选择 Search、Extract、
Map、Crawl、Research、LLM Context、News 等能力组合。
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import httpx

from .base import BaseTool, ToolResult, ToolType


DEFAULT_LEGAL_WARNING = "联网资料仅供检索线索和内部研究，需律师核验后才能作为法律依据。"


@dataclass
class ExternalSearchSource:
    """统一后的联网资料来源。"""

    provider: str
    tool: str
    title: str = ""
    url: str = ""
    content: str = ""
    snippet: str = ""
    score: float = 0.0
    published_date: str = ""
    source_type: str = "web"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "tool": self.tool,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "snippet": self.snippet,
            "score": self.score,
            "published_date": self.published_date,
            "source_type": self.source_type,
            "metadata": self.metadata,
        }


@dataclass
class ExternalResearchResult:
    """统一后的联网研究结果。"""

    query: str
    purpose: str
    answer: str = ""
    sources: List[ExternalSearchSource] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    providers_used: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return bool(self.answer.strip() or self.sources)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "query": self.query,
            "purpose": self.purpose,
            "answer": self.answer,
            "sources": [source.to_dict() for source in self.sources],
            "tool_calls": self.tool_calls,
            "providers_used": self.providers_used,
            "warnings": self.warnings,
            "usage": self.usage,
        }


class TavilyResearchClient:
    """Tavily Python SDK 的异步薄封装。"""

    def __init__(
        self,
        api_key: str,
        project_id: str = "",
        timeout: int = 20,
    ):
        self.api_key = api_key
        self.project_id = project_id
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from tavily import AsyncTavilyClient
            except ImportError as exc:  # pragma: no cover - 仅真实环境缺依赖时触发
                raise RuntimeError(
                    "tavily-python is required when TAVILY_API_KEY is configured"
                ) from exc

            kwargs = {"api_key": self.api_key}
            if self.project_id:
                kwargs["project_id"] = self.project_id
            self._client = AsyncTavilyClient(**kwargs)
        return self._client

    async def search_sources(
        self,
        query: str,
        topic: str = "general",
        max_results: int = 5,
        search_depth: str = "basic",
        freshness: str = "",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_answer: bool | str = False,
    ) -> dict:
        params = _drop_none(
            {
                "query": query,
                "topic": topic,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_domains": include_domains or None,
                "exclude_domains": exclude_domains or None,
                "include_answer": include_answer,
                "include_usage": True,
                "include_favicon": True,
                "time_range": _to_tavily_time_range(freshness),
            }
        )
        data = await self._maybe_await(self._get_client().search(**params))
        return {
            "answer": str(data.get("answer") or ""),
            "sources": _sources_from_tavily(data, "search", topic),
            "usage": data.get("usage") or {},
            "raw": data,
        }

    async def extract_sources(
        self,
        urls: List[str],
        query: str = "",
        extract_depth: str = "basic",
    ) -> dict:
        if not urls:
            return {"sources": [], "usage": {}}
        params = _drop_none(
            {
                "urls": urls[:20],
                "query": query or None,
                "extract_depth": extract_depth,
                "format": "markdown",
                "include_usage": True,
                "include_favicon": True,
            }
        )
        data = await self._maybe_await(self._get_client().extract(**params))
        return {
            "sources": _sources_from_tavily_extract(data),
            "usage": data.get("usage") or {},
            "raw": data,
        }

    async def map_site(
        self,
        site_url: str,
        query: str = "",
        max_results: int = 20,
    ) -> dict:
        params = _drop_none(
            {
                "url": site_url,
                "instructions": f"Find pages related to: {query}" if query else None,
                "limit": max_results,
            }
        )
        data = await self._maybe_await(self._get_client().map(**params))
        return {"sources": _sources_from_tavily_map(data), "usage": {}, "raw": data}

    async def crawl_site(
        self,
        site_url: str,
        query: str = "",
        max_results: int = 10,
    ) -> dict:
        params = _drop_none(
            {
                "url": site_url,
                "instructions": f"Collect pages related to: {query}" if query else None,
                "max_depth": 2,
                "limit": max_results,
                "extract_depth": "basic",
                "format": "markdown",
                "include_usage": True,
            }
        )
        data = await self._maybe_await(self._get_client().crawl(**params))
        return {
            "sources": _sources_from_generic_results(data, "tavily", "crawl", "site"),
            "usage": data.get("usage") if isinstance(data, dict) else {},
            "raw": data,
        }

    async def research_report(self, query: str, max_results: int = 5) -> dict:
        client = self._get_client()
        if not hasattr(client, "research"):
            search = await self.search_sources(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_answer="advanced",
            )
            search["metadata"] = {"fallback": "search"}
            return search

        data = await self._maybe_await(client.research(input=query))
        if not isinstance(data, dict):
            data = {"content": str(data)}
        return {
            "answer": str(data.get("content") or data.get("answer") or ""),
            "sources": _sources_from_generic_results(data, "tavily", "research", "research"),
            "usage": data.get("usage") or {},
            "raw": data,
        }

    async def usage(self) -> dict:
        client = self._get_client()
        if not hasattr(client, "usage"):
            return {}
        data = await self._maybe_await(client.usage())
        return data if isinstance(data, dict) else {"value": data}

    async def close(self) -> None:
        client = self._client
        close = getattr(client, "close", None) or getattr(client, "aclose", None)
        if close:
            await self._maybe_await(close())

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value


class BraveContextClient:
    """Brave Search API 的异步客户端。"""

    def __init__(self, api_key: str, timeout: int = 20, max_tokens: int = 8192):
        self.api_key = api_key
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.base_url = "https://api.search.brave.com/res"
        self._client = httpx.AsyncClient(timeout=timeout)

    async def llm_context(
        self,
        query: str,
        max_results: int = 5,
        freshness: str = "",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> dict:
        payload = _drop_none(
            {
                "q": _with_domain_filters(query, include_domains, exclude_domains),
                "count": max_results,
                "maximum_number_of_urls": max_results,
                "maximum_number_of_tokens": self.max_tokens,
                "freshness": _to_brave_freshness(freshness),
                "context_threshold_mode": "balanced",
            }
        )
        data = await self._request("POST", "/v1/llm/context", json=payload)
        return {
            "answer": _extract_brave_context_text(data),
            "sources": _sources_from_brave(data, "llm_context", "context"),
            "usage": data.get("usage") or {},
            "raw": data,
        }

    async def web_search(
        self,
        query: str,
        max_results: int = 5,
        freshness: str = "",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> dict:
        params = _drop_none(
            {
                "q": _with_domain_filters(query, include_domains, exclude_domains),
                "count": max_results,
                "freshness": _to_brave_freshness(freshness),
                "result_filter": "web",
                "search_lang": "zh",
                "ui_lang": "zh-CN",
            }
        )
        data = await self._request("GET", "/v1/web/search", params=params)
        return {"sources": _sources_from_brave(data, "web_search", "web"), "usage": {}, "raw": data}

    async def news_search(
        self,
        query: str,
        max_results: int = 5,
        freshness: str = "",
    ) -> dict:
        params = _drop_none(
            {
                "q": query,
                "count": max_results,
                "freshness": _to_brave_freshness(freshness or "week"),
                "search_lang": "zh",
                "ui_lang": "zh-CN",
            }
        )
        data = await self._request("GET", "/v1/news/search", params=params)
        return {"sources": _sources_from_brave(data, "news_search", "news"), "usage": {}, "raw": data}

    async def place_search(self, query: str, max_results: int = 5) -> dict:
        params = {"q": query, "count": max_results}
        data = await self._request("GET", "/v1/local/place_search", params=params)
        return {"sources": _sources_from_brave(data, "place_search", "place"), "usage": {}, "raw": data}

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        response = await self._client.request(
            method=method,
            url=f"{self.base_url}{path}",
            headers=headers,
            params=params,
            json=json,
        )
        response.raise_for_status()
        return response.json()


class ExternalResearchTool(BaseTool):
    """按任务目的聚合 Tavily 和 Brave 多工具能力。"""

    name = "external_research"
    description = "按研究目的调用 Tavily/Brave 的联网搜索、提取、研究、站点采集和上下文工具"
    tool_type = ToolType.RAG

    def __init__(
        self,
        tavily_client: Optional[Any] = None,
        brave_client: Optional[Any] = None,
        enabled: bool = False,
        max_results: int = 5,
        max_tokens: int = 8192,
    ):
        self.tavily = tavily_client
        self.brave = brave_client
        self.enabled = enabled
        self.max_results = max_results
        self.max_tokens = max_tokens

    def is_available(self) -> bool:
        return self.enabled and bool(self.tavily or self.brave)

    async def execute(
        self,
        query: str,
        purpose: str = "quick_search",
        urls: Optional[List[str]] = None,
        site_url: str = "",
        providers: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        freshness: str = "",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> ToolResult:
        if not self.is_available():
            return ToolResult(
                success=False,
                error="external research is disabled or no provider is configured",
            )

        purpose = purpose or "quick_search"
        result = ExternalResearchResult(
            query=query,
            purpose=purpose,
            warnings=[DEFAULT_LEGAL_WARNING],
        )
        requested = set(providers or ["tavily", "brave"])
        limit = max(1, min(max_results or self.max_results, 20))
        urls = _clean_list(urls)
        include_domains = _clean_list(include_domains)
        exclude_domains = _clean_list(exclude_domains)

        try:
            await self._route(
                result=result,
                query=query,
                purpose=purpose,
                urls=urls,
                site_url=site_url,
                providers=requested,
                max_results=limit,
                freshness=freshness,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
            )
        except Exception as exc:
            result.warnings.append(f"联网研究路由失败：{type(exc).__name__}")

        result.sources = self._dedupe_sources(result.sources)
        if not result.answer and result.sources:
            result.answer = f"已获取 {len(result.sources)} 条联网资料，请结合来源逐条核验。"
        if DEFAULT_LEGAL_WARNING not in result.warnings:
            result.warnings.append(DEFAULT_LEGAL_WARNING)

        data = result.to_dict()
        return ToolResult(success=result.success, data=data, metadata={"purpose": purpose})

    async def _route(
        self,
        result: ExternalResearchResult,
        query: str,
        purpose: str,
        urls: List[str],
        site_url: str,
        providers: set[str],
        max_results: int,
        freshness: str,
        include_domains: List[str],
        exclude_domains: List[str],
    ) -> None:
        if purpose == "deep_research":
            await self._tavily_research(result, query, max_results, providers)
            await self._brave_context(result, query, max_results, freshness, providers, include_domains, exclude_domains)
            return

        if purpose == "extract_url":
            await self._tavily_extract(result, urls, query, providers, extract_depth="advanced")
            if query:
                await self._brave_context(result, query, max_results, freshness, providers, include_domains, exclude_domains)
            return

        if purpose == "site_discovery":
            await self._tavily_map(result, site_url or query, query, max_results, providers)
            await self._brave_web(result, _site_query(site_url, query), max_results, freshness, providers, [], [])
            await self._tavily_extract(result, _top_urls(result.sources, 3), query, providers)
            return

        if purpose == "site_crawl":
            await self._tavily_crawl(result, site_url or query, query, max_results, providers)
            await self._brave_context(result, _site_query(site_url, query), max_results, freshness, providers, [], [])
            return

        if purpose == "news_check":
            await self._tavily_search(result, query, max_results, freshness, providers, "news", include_domains, exclude_domains)
            await self._brave_news(result, query, max_results, freshness, providers)
            await self._brave_context(result, query, max_results, freshness or "week", providers, include_domains, exclude_domains)
            return

        if purpose == "place_or_entity":
            await self._brave_place(result, query, max_results, providers)
            await self._brave_web(result, query, max_results, freshness, providers, include_domains, exclude_domains)
            await self._tavily_search(result, query, max_results, freshness, providers, "general", include_domains, exclude_domains)
            return

        if purpose == "legal_source_check":
            await self._tavily_search(result, query, max_results, freshness, providers, "general", include_domains, exclude_domains)
            await self._brave_web(result, query, max_results, freshness, providers, include_domains, exclude_domains)
            await self._tavily_extract(result, _top_urls(result.sources, 3), query, providers)
            await self._brave_context(result, query, max_results, freshness, providers, include_domains, exclude_domains)
            return

        await self._tavily_search(result, query, max_results, freshness, providers, "general", include_domains, exclude_domains)
        await self._brave_web(result, query, max_results, freshness, providers, include_domains, exclude_domains)
        await self._tavily_extract(result, _top_urls(result.sources, 2), query, providers)
        await self._brave_context(result, query, max_results, freshness, providers, include_domains, exclude_domains)

    async def _run_provider_call(
        self,
        result: ExternalResearchResult,
        provider: str,
        tool: str,
        coro: Any,
    ) -> Optional[dict]:
        label = f"{provider}.{tool}"
        try:
            payload = await coro
            if payload is None:
                payload = {}
            self._merge_payload(result, provider, label, payload)
            result.tool_calls.append(
                {
                    "provider": provider,
                    "tool": tool,
                    "status": "ok",
                    "count": len(payload.get("sources") or []),
                }
            )
            return payload
        except Exception as exc:
            result.tool_calls.append(
                {
                    "provider": provider,
                    "tool": tool,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            result.warnings.append(f"{label} 调用失败：{type(exc).__name__}")
            return None

    def _merge_payload(
        self,
        result: ExternalResearchResult,
        provider: str,
        label: str,
        payload: dict,
    ) -> None:
        if provider not in result.providers_used:
            result.providers_used.append(provider)
        if payload.get("answer") and not result.answer:
            result.answer = str(payload["answer"]).strip()
        for source in payload.get("sources") or []:
            result.sources.append(_coerce_source(source, provider, label))
        if payload.get("usage"):
            result.usage[label] = payload["usage"]

    async def _tavily_search(self, result, query, max_results, freshness, providers, topic, include_domains, exclude_domains):
        if "tavily" in providers and self.tavily:
            await self._run_provider_call(
                result,
                "tavily",
                f"search:{topic}",
                self.tavily.search_sources(
                    query=query,
                    topic=topic,
                    max_results=max_results,
                    search_depth="advanced" if topic == "news" else "basic",
                    freshness=freshness,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                    include_answer=False,
                ),
            )

    async def _tavily_extract(self, result, urls, query, providers, extract_depth="basic"):
        if "tavily" in providers and self.tavily and urls:
            await self._run_provider_call(
                result,
                "tavily",
                "extract",
                self.tavily.extract_sources(urls=urls, query=query, extract_depth=extract_depth),
            )

    async def _tavily_map(self, result, site_url, query, max_results, providers):
        if "tavily" in providers and self.tavily and site_url:
            await self._run_provider_call(
                result,
                "tavily",
                "map",
                self.tavily.map_site(site_url=_normalize_site_url(site_url), query=query, max_results=max_results),
            )

    async def _tavily_crawl(self, result, site_url, query, max_results, providers):
        if "tavily" in providers and self.tavily and site_url:
            await self._run_provider_call(
                result,
                "tavily",
                "crawl",
                self.tavily.crawl_site(site_url=_normalize_site_url(site_url), query=query, max_results=max_results),
            )

    async def _tavily_research(self, result, query, max_results, providers):
        if "tavily" in providers and self.tavily:
            await self._run_provider_call(
                result,
                "tavily",
                "research",
                self.tavily.research_report(query=query, max_results=max_results),
            )

    async def _brave_context(self, result, query, max_results, freshness, providers, include_domains, exclude_domains):
        if "brave" in providers and self.brave:
            await self._run_provider_call(
                result,
                "brave",
                "llm_context",
                self.brave.llm_context(
                    query=query,
                    max_results=max_results,
                    freshness=freshness,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                ),
            )

    async def _brave_web(self, result, query, max_results, freshness, providers, include_domains, exclude_domains):
        if "brave" in providers and self.brave:
            await self._run_provider_call(
                result,
                "brave",
                "web_search",
                self.brave.web_search(
                    query=query,
                    max_results=max_results,
                    freshness=freshness,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                ),
            )

    async def _brave_news(self, result, query, max_results, freshness, providers):
        if "brave" in providers and self.brave:
            await self._run_provider_call(
                result,
                "brave",
                "news_search",
                self.brave.news_search(query=query, max_results=max_results, freshness=freshness),
            )

    async def _brave_place(self, result, query, max_results, providers):
        if "brave" in providers and self.brave:
            await self._run_provider_call(
                result,
                "brave",
                "place_search",
                self.brave.place_search(query=query, max_results=max_results),
            )

    def _dedupe_sources(self, sources: List[ExternalSearchSource]) -> List[ExternalSearchSource]:
        seen = set()
        deduped = []
        for source in sources:
            key = (source.url or f"{source.provider}:{source.title}:{source.content[:80]}").strip()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)
        return sorted(deduped, key=lambda item: item.score or 0.0, reverse=True)

    async def close(self) -> None:
        for client in [self.tavily, self.brave]:
            close = getattr(client, "close", None)
            if close:
                value = close()
                if inspect.isawaitable(value):
                    await value


def create_external_research_tool(config: Any) -> Optional[ExternalResearchTool]:
    """按配置创建联网研究工具。"""
    if not getattr(config, "enabled", False):
        return None

    tavily = None
    brave = None
    if getattr(config, "tavily_api_key", ""):
        tavily = TavilyResearchClient(
            api_key=config.tavily_api_key,
            project_id=getattr(config, "tavily_project_id", ""),
            timeout=getattr(config, "timeout", 20),
        )
    if getattr(config, "brave_search_api_key", ""):
        brave = BraveContextClient(
            api_key=config.brave_search_api_key,
            timeout=getattr(config, "timeout", 20),
            max_tokens=getattr(config, "max_tokens", 8192),
        )

    if not tavily and not brave:
        return None
    return ExternalResearchTool(
        tavily_client=tavily,
        brave_client=brave,
        enabled=True,
        max_results=getattr(config, "max_results", 5),
        max_tokens=getattr(config, "max_tokens", 8192),
    )


def _drop_none(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None and value != ""}


def _clean_list(values: Optional[Iterable[str]]) -> List[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def _to_tavily_time_range(freshness: str) -> Optional[str]:
    mapping = {
        "pd": "day",
        "day": "day",
        "d": "day",
        "pw": "week",
        "week": "week",
        "w": "week",
        "pm": "month",
        "month": "month",
        "m": "month",
        "py": "year",
        "year": "year",
        "y": "year",
    }
    return mapping.get((freshness or "").strip().lower())


def _to_brave_freshness(freshness: str) -> Optional[str]:
    mapping = {
        "day": "pd",
        "d": "pd",
        "pd": "pd",
        "week": "pw",
        "w": "pw",
        "pw": "pw",
        "month": "pm",
        "m": "pm",
        "pm": "pm",
        "year": "py",
        "y": "py",
        "py": "py",
    }
    return mapping.get((freshness or "").strip().lower(), freshness or None)


def _with_domain_filters(
    query: str,
    include_domains: Optional[List[str]],
    exclude_domains: Optional[List[str]],
) -> str:
    terms = [query]
    terms.extend(f"site:{domain}" for domain in include_domains or [])
    terms.extend(f"-site:{domain}" for domain in exclude_domains or [])
    return " ".join(term for term in terms if term)


def _site_query(site_url: str, query: str) -> str:
    return " ".join(part for part in [query, f"site:{_site_domain(site_url)}" if site_url else ""] if part)


def _normalize_site_url(site_url: str) -> str:
    if site_url.startswith(("http://", "https://")):
        return site_url
    return f"https://{site_url}"


def _site_domain(site_url: str) -> str:
    return site_url.replace("https://", "").replace("http://", "").split("/")[0]


def _top_urls(sources: List[ExternalSearchSource], limit: int) -> List[str]:
    urls = []
    for source in sources:
        if source.url and source.url not in urls:
            urls.append(source.url)
        if len(urls) >= limit:
            break
    return urls


def _coerce_source(source: Any, provider: str, label: str) -> ExternalSearchSource:
    if isinstance(source, ExternalSearchSource):
        return source
    if isinstance(source, dict):
        return ExternalSearchSource(
            provider=str(source.get("provider") or provider),
            tool=str(source.get("tool") or label),
            title=str(source.get("title") or ""),
            url=str(source.get("url") or ""),
            content=str(source.get("content") or source.get("raw_content") or ""),
            snippet=str(source.get("snippet") or source.get("description") or ""),
            score=float(source.get("score") or source.get("relevance_score") or 0.0),
            published_date=str(source.get("published_date") or source.get("age") or ""),
            source_type=str(source.get("source_type") or "web"),
            metadata=dict(source.get("metadata") or {}),
        )
    return ExternalSearchSource(provider=provider, tool=label, content=str(source))


def _sources_from_tavily(data: dict, tool: str, source_type: str) -> List[ExternalSearchSource]:
    return [
        ExternalSearchSource(
            provider="tavily",
            tool=tool,
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            content=str(item.get("content") or item.get("raw_content") or ""),
            snippet=str(item.get("content") or "")[:300],
            score=float(item.get("score") or 0.0),
            published_date=str(item.get("published_date") or ""),
            source_type=source_type,
            metadata={key: value for key, value in item.items() if key not in {"title", "url", "content", "raw_content"}},
        )
        for item in data.get("results", [])
        if isinstance(item, dict)
    ]


def _sources_from_tavily_extract(data: dict) -> List[ExternalSearchSource]:
    return [
        ExternalSearchSource(
            provider="tavily",
            tool="extract",
            title=str(item.get("title") or item.get("url") or ""),
            url=str(item.get("url") or ""),
            content=str(item.get("raw_content") or item.get("content") or ""),
            snippet=str(item.get("raw_content") or item.get("content") or "")[:300],
            source_type="extract",
            metadata={key: value for key, value in item.items() if key not in {"title", "url", "content", "raw_content"}},
        )
        for item in data.get("results", [])
        if isinstance(item, dict)
    ]


def _sources_from_tavily_map(data: Any) -> List[ExternalSearchSource]:
    if isinstance(data, list):
        urls = data
    elif isinstance(data, dict):
        urls = data.get("results") or data.get("urls") or []
    else:
        urls = []

    sources = []
    for item in urls:
        if isinstance(item, dict):
            url = str(item.get("url") or item.get("href") or "")
            title = str(item.get("title") or url)
        else:
            url = str(item)
            title = url
        if url:
            sources.append(
                ExternalSearchSource(
                    provider="tavily",
                    tool="map",
                    title=title,
                    url=url,
                    source_type="site",
                    metadata=item if isinstance(item, dict) else {},
                )
            )
    return sources


def _sources_from_generic_results(
    data: Any,
    provider: str,
    tool: str,
    source_type: str,
) -> List[ExternalSearchSource]:
    if not isinstance(data, dict):
        return []
    items = data.get("sources") or data.get("results") or []
    sources = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sources.append(
            ExternalSearchSource(
                provider=provider,
                tool=tool,
                title=str(item.get("title") or item.get("url") or ""),
                url=str(item.get("url") or ""),
                content=str(item.get("content") or item.get("raw_content") or item.get("snippet") or ""),
                snippet=str(item.get("snippet") or item.get("content") or "")[:300],
                score=float(item.get("score") or 0.0),
                published_date=str(item.get("published_date") or ""),
                source_type=source_type,
                metadata=item,
            )
        )
    return sources


def _extract_brave_context_text(data: dict) -> str:
    for key in ["answer", "context", "summary", "text"]:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _sources_from_brave(data: dict, tool: str, source_type: str) -> List[ExternalSearchSource]:
    items: List[dict] = []
    if isinstance(data.get("results"), list):
        items.extend(data["results"])
    for group_key in ["web", "news", "videos", "locations", "places"]:
        group = data.get(group_key)
        if isinstance(group, dict) and isinstance(group.get("results"), list):
            items.extend(group["results"])
        elif isinstance(group, list):
            items.extend(group)
    if isinstance(data.get("sources"), list):
        items.extend(data["sources"])

    sources = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("content") or item.get("description") or item.get("snippet") or item.get("text") or ""
        url = item.get("url") or item.get("link") or item.get("profile") or ""
        sources.append(
            ExternalSearchSource(
                provider="brave",
                tool=tool,
                title=str(item.get("title") or item.get("name") or url),
                url=str(url),
                content=str(content),
                snippet=str(content)[:300],
                score=float(item.get("score") or 0.0),
                published_date=str(item.get("age") or item.get("page_age") or item.get("published_date") or ""),
                source_type=source_type,
                metadata=item,
            )
        )
    return sources
