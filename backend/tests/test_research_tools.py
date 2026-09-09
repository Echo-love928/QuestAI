import pytest

from app.core.config import Settings
from app.core.exceptions import ExtractUnavailable, ResearchBudgetExceeded, SearchUnavailable
from app.research.budget import ResearchBudget
from app.research.models import ExtractToolInput, SearchToolInput
from app.research.tools import TavilyExtractAdapter, TavilySearchAdapter


def settings() -> Settings:
    return Settings(
        _env_file=None,
        tavily_api_key="test-key",
        web_research_enabled=True,
        deepseek_api_key="test-deepseek-key",
        jwt_secret="test-jwt-secret-that-is-at-least-32-chars",
        cors_origins=["http://localhost:10086"],
    )


class FakeTool:
    instances = []
    response = {"results": []}

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.calls = []
        self.__class__.instances.append(self)

    async def ainvoke(self, payload):
        self.calls.append(payload)
        return self.__class__.response


class FailingTool(FakeTool):
    async def ainvoke(self, payload):
        raise RuntimeError("upstream leaked details")


@pytest.mark.anyio
async def test_search_adapter_builds_dynamic_official_tool_configuration() -> None:
    FakeTool.instances.clear()
    FakeTool.response = {
        "results": [
            {
                "title": "Official guide",
                "url": "https://example.com/guide",
                "content": "Current guide content",
                "score": 0.9,
            }
        ],
        "request_id": "req-search",
    }
    adapter = TavilySearchAdapter(settings(), tool_factory=FakeTool)

    result = await adapter.search(
        SearchToolInput(
            query="Harness Engineering",
            complexity="complex",
            search_depth="advanced",
            max_results=7,
            chunks_per_source=3,
            country="china",
            language="zh-cn",
            filter_by_language=False,
        )
    )

    tool = FakeTool.instances[-1]
    assert tool.kwargs["max_results"] == 7
    assert tool.kwargs["country"] == "china"
    assert tool.kwargs["include_raw_content"] is False
    assert tool.kwargs["api_wrapper"].tavily_api_key.get_secret_value() == "test-key"
    assert tool.calls[0]["language"] == "zh-cn"
    assert tool.calls[0]["filter_by_language"] is False
    assert tool.calls[0]["chunks_per_source"] == 3
    assert result["request_id"] == "req-search"


@pytest.mark.anyio
async def test_search_adapter_wraps_upstream_error() -> None:
    adapter = TavilySearchAdapter(settings(), tool_factory=FailingTool)

    with pytest.raises(SearchUnavailable, match="网络搜索暂时不可用"):
        await adapter.search(SearchToolInput(query="test topic"))


@pytest.mark.anyio
async def test_search_adapter_log_does_not_expose_upstream_detail(caplog) -> None:
    adapter = TavilySearchAdapter(settings(), tool_factory=FailingTool)

    with caplog.at_level("WARNING", logger="app.research.tools"):
        with pytest.raises(SearchUnavailable):
            await adapter.search(SearchToolInput(query="test topic"))

    assert "upstream leaked details" not in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.anyio
async def test_extract_adapter_preserves_partial_success() -> None:
    FakeTool.instances.clear()
    FakeTool.response = {
        "results": [
            {"url": "https://example.com/a", "raw_content": "page A"}
        ],
        "failed_results": [
            {"url": "https://example.com/b", "error": "blocked"}
        ],
        "request_id": "req-extract",
    }
    adapter = TavilyExtractAdapter(
        settings(),
        tool_factory=FakeTool,
        url_validator=lambda value: value,
    )

    result = await adapter.extract(
        ExtractToolInput(
            urls=["https://example.com/a", "https://example.com/b"],
            extract_depth="advanced",
            query="relevant section",
            chunks_per_source=4,
        )
    )

    tool = FakeTool.instances[-1]
    assert tool.kwargs["extract_depth"] == "advanced"
    assert tool.kwargs["chunks_per_source"] == 4
    assert tool.kwargs["apiwrapper"].tavily_api_key.get_secret_value() == "test-key"
    assert len(result["results"]) == 1
    assert len(result["failed_results"]) == 1


@pytest.mark.anyio
async def test_extract_adapter_rejects_all_failed_results() -> None:
    FakeTool.response = {
        "results": [],
        "failed_results": [{"url": "https://example.com/a", "error": "blocked"}],
    }
    adapter = TavilyExtractAdapter(
        settings(), tool_factory=FakeTool, url_validator=lambda value: value
    )

    with pytest.raises(ExtractUnavailable, match="网页内容暂时无法获取"):
        await adapter.extract(ExtractToolInput(urls=["https://example.com/a"]))


@pytest.mark.anyio
async def test_extract_adapter_revalidates_final_redirect_url() -> None:
    FakeTool.response = {
        "results": [{"url": "http://127.0.0.1/internal", "raw_content": "secret"}],
        "failed_results": [],
    }

    def validator(value: str) -> str:
        if "127.0.0.1" in value:
            raise ValueError("private redirect")
        return value

    adapter = TavilyExtractAdapter(
        settings(), tool_factory=FakeTool, url_validator=validator
    )

    with pytest.raises(ExtractUnavailable):
        await adapter.extract(ExtractToolInput(urls=["https://example.com/a"]))


def test_budget_enforces_total_search_and_unique_url_limits() -> None:
    budget = ResearchBudget(max_tool_calls=4, max_search_calls=2, max_extract_urls=3)
    budget.claim_search()
    budget.claim_search()
    with pytest.raises(ResearchBudgetExceeded):
        budget.claim_search()

    budget.claim_extract(["https://a.example", "https://b.example"])
    budget.claim_extract(["https://b.example", "https://c.example"])
    with pytest.raises(ResearchBudgetExceeded):
        budget.claim_extract(["https://d.example"])
