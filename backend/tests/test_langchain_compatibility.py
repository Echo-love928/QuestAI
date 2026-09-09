import inspect

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_deepseek import ChatDeepSeek
from langchain_tavily import TavilyExtract, TavilySearch


@tool
def compatibility_lookup(query: str) -> str:
    """Return deterministic content for an offline compatibility test."""

    return f"result:{query}"


def test_chat_deepseek_can_build_agent_and_bind_tools() -> None:
    model = ChatDeepSeek(
        model="deepseek-chat",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        max_retries=0,
    )

    agent = create_agent(model=model, tools=[compatibility_lookup])
    bound_model = model.bind_tools([compatibility_lookup])

    assert agent is not None
    assert bound_model is not None


def test_tavily_tools_expose_native_async(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    search = TavilySearch(max_results=3, search_depth="basic")
    extract = TavilyExtract(extract_depth="basic")

    assert inspect.iscoroutinefunction(search._arun)
    assert inspect.iscoroutinefunction(extract._arun)
