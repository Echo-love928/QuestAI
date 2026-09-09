import asyncio
import logging
from collections.abc import Callable
from typing import Any

from langchain_tavily import TavilyExtract, TavilySearch
from langchain_tavily._utilities import (
    TavilyExtractAPIWrapper,
    TavilySearchAPIWrapper,
)

from app.core.config import Settings
from app.core.exceptions import ExtractUnavailable, SearchUnavailable
from app.research.models import ExtractToolInput, SearchToolInput
from app.research.safety import validate_public_url


logger = logging.getLogger(__name__)


class TavilySearchAdapter:
    def __init__(
        self, settings: Settings, *, tool_factory: Callable[..., Any] = TavilySearch
    ) -> None:
        self.settings = settings
        self.tool_factory = tool_factory

    async def search(self, params: SearchToolInput) -> dict[str, Any]:
        max_results = min(params.max_results, self.settings.research_max_search_results)
        tool = self.tool_factory(
            api_wrapper=TavilySearchAPIWrapper(
                tavily_api_key=self.settings.tavily_api_key
            ),
            max_results=max_results,
            topic=params.topic,
            search_depth=params.search_depth,
            include_answer=False,
            include_raw_content=False,
            include_images=False,
            country=params.country,
            handle_tool_error=False,
        )
        payload = {
            "query": params.query,
            "include_domains": params.include_domains,
            "exclude_domains": params.exclude_domains,
            "search_depth": params.search_depth,
            "include_images": False,
            "time_range": params.time_range,
            "topic": params.topic,
            "chunks_per_source": params.chunks_per_source,
            "language": params.language,
            "filter_by_language": params.filter_by_language,
        }
        try:
            result = await asyncio.wait_for(
                tool.ainvoke(payload), timeout=self.settings.research_tool_timeout_seconds
            )
        except Exception as exc:
            logger.warning("tavily search failed: %s", type(exc).__name__)
            raise SearchUnavailable("网络搜索暂时不可用") from exc
        if not isinstance(result, dict) or result.get("error") or not result.get("results"):
            raise SearchUnavailable("网络搜索暂时不可用")
        return result


class TavilyExtractAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        tool_factory: Callable[..., Any] = TavilyExtract,
        url_validator: Callable[[str], str] = validate_public_url,
    ) -> None:
        self.settings = settings
        self.tool_factory = tool_factory
        self.url_validator = url_validator

    async def extract(self, params: ExtractToolInput) -> dict[str, Any]:
        urls = [self.url_validator(url) for url in params.urls]
        urls = list(dict.fromkeys(urls))[: self.settings.research_max_extract_urls]
        tool = self.tool_factory(
            apiwrapper=TavilyExtractAPIWrapper(
                tavily_api_key=self.settings.tavily_api_key
            ),
            extract_depth=params.extract_depth,
            include_images=False,
            format="markdown",
            chunks_per_source=params.chunks_per_source,
            handle_tool_error=False,
        )
        payload = {
            "urls": urls,
            "extract_depth": params.extract_depth,
            "include_images": False,
            "query": params.query,
        }
        try:
            result = await asyncio.wait_for(
                tool.ainvoke(payload), timeout=self.settings.research_tool_timeout_seconds
            )
        except Exception as exc:
            logger.warning("tavily extract failed: %s", type(exc).__name__)
            raise ExtractUnavailable("网页内容暂时无法获取") from exc
        if not isinstance(result, dict) or result.get("error") or not result.get("results"):
            raise ExtractUnavailable("网页内容暂时无法获取")
        safe_results = []
        for item in result.get("results") or []:
            if not isinstance(item, dict):
                continue
            try:
                final_url = self.url_validator(str(item.get("url") or ""))
            except ValueError:
                continue
            safe_results.append({**item, "url": final_url})
        if not safe_results:
            raise ExtractUnavailable("网页内容暂时无法获取")
        result = {**result, "results": safe_results}
        return result
