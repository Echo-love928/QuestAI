import json

import pytest
from langchain.messages import AIMessage

from app.core.config import Settings
from app.core.exceptions import ResearchUnavailable
from app.models.quiz import QuizGenerateRequest
from app.research.agent import ResearchAgent, _brief_from_agent_state
from app.research.models import ResearchBrief, ResearchFact


def settings() -> Settings:
    return Settings(
        _env_file=None,
        tavily_api_key="test-key",
        web_research_enabled=True,
        deepseek_api_key="test-deepseek-key",
        jwt_secret="test-jwt-secret-that-is-at-least-32-chars",
        cors_origins=["http://localhost:10086"],
    )


def test_deepseek_v4_agent_disables_thinking_for_langchain_tool_choice(monkeypatch) -> None:
    captured = {}

    def fake_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.research.agent.ChatDeepSeek", fake_model)
    ResearchAgent(settings())

    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


def test_agent_brief_parser_accepts_text_blocks_and_surrounding_copy() -> None:
    payload = ResearchBrief(
        resolved_topic="Harness Engineering",
        domain="software engineering",
        is_ambiguous=False,
        is_sufficient=True,
        summary="current practice",
        key_facts=[ResearchFact(text="fact", source_ids=["src_1"])],
        first_party_source_ids=["src_1"],
    ).model_dump_json()
    state = {"messages": [AIMessage(content=[{"type": "text", "text": f"结果如下：\n{payload}"}])]}

    assert _brief_from_agent_state(state).resolved_topic == "Harness Engineering"


class FakeSearchAdapter:
    async def search(self, params):
        return {
            "results": [
                {
                    "title": "Official topic guide",
                    "url": "https://example.com/topic",
                    "content": f"current evidence for {params.query}",
                    "score": 0.95,
                }
            ]
        }


class FakeExtractAdapter:
    async def extract(self, params):
        return {
            "results": [
                {"url": url, "raw_content": f"full page for {url}"}
                for url in params.urls
            ],
            "failed_results": [],
        }


class ScriptedAgent:
    def __init__(self, tools, sequence, calls):
        self.tools = {tool.name: tool for tool in tools}
        self.sequence = sequence
        self.calls = calls

    async def ainvoke(self, _state, config=None):
        source_ids = []
        for name in self.sequence:
            if name == "search":
                payload = {
                    "query": "Harness Engineering",
                    "complexity": "complex" if "extract" in self.sequence else "simple",
                    "search_depth": "advanced" if "extract" in self.sequence else "basic",
                    "max_results": 5 if "extract" in self.sequence else 3,
                    "chunks_per_source": 2,
                }
                result = await self.tools["tavily_search"].ainvoke(payload)
            else:
                result = await self.tools["tavily_extract"].ainvoke(
                    {
                        "urls": ["https://example.com/topic"],
                        "extract_depth": "advanced",
                        "query": "Harness Engineering",
                        "chunks_per_source": 3,
                    }
                )
            self.calls.append(name)
            source_ids.extend(item["source_id"] for item in json.loads(result))
        source_ids = list(dict.fromkeys(source_ids))
        return {
            "structured_response": ResearchBrief(
                resolved_topic="Harness Engineering",
                domain="AI software engineering",
                is_ambiguous=False,
                is_sufficient=True,
                summary="Evidence is sufficient.",
                key_facts=[
                    ResearchFact(text="Grounded current fact", source_ids=source_ids)
                ],
                first_party_source_ids=[source_ids[0]],
            )
        }


class ScriptedFactory:
    def __init__(self, sequence):
        self.sequence = sequence
        self.calls = []
        self.tool_names = []

    def __call__(self, *, tools, **_kwargs):
        self.tool_names = [tool.name for tool in tools]
        return ScriptedAgent(tools, self.sequence, self.calls)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("quiz_request", "sequence", "expected_mode"),
    [
        (
            QuizGenerateRequest(user_input="Harness Engineering 是什么"),
            ["search"],
            "web_search",
        ),
        (
            QuizGenerateRequest(user_input="Harness Engineering 深入原理"),
            ["search", "extract"],
            "mixed",
        ),
        (
            QuizGenerateRequest(
                user_input="https://example.com/topic", source_type="url"
            ),
            ["extract"],
            "url_extract",
        ),
    ],
)
async def test_agent_can_choose_search_extract_or_combined_path(
    quiz_request, sequence, expected_mode
) -> None:
    factory = ScriptedFactory(sequence)
    researcher = ResearchAgent(
        settings(),
        model=object(),
        search_adapter=FakeSearchAdapter(),
        extract_adapter=FakeExtractAdapter(),
        agent_factory=factory,
        url_validator=lambda value: value,
    )

    result = await researcher.research(quiz_request)

    assert factory.tool_names == ["tavily_search", "tavily_extract"]
    assert factory.calls == sequence
    assert result.grounding_mode == expected_mode
    assert result.brief is not None
    assert result.sources


@pytest.mark.anyio
async def test_complete_material_skips_agent() -> None:
    factory = ScriptedFactory(["search"])
    researcher = ResearchAgent(
        settings(),
        model=object(),
        search_adapter=FakeSearchAdapter(),
        extract_adapter=FakeExtractAdapter(),
        agent_factory=factory,
        url_validator=lambda value: value,
    )

    result = await researcher.research(
        QuizGenerateRequest(user_input="这是一段完整、稳定的学习资料。" * 30)
    )

    assert result.grounding_mode == "user_content"
    assert result.sources == []
    assert factory.calls == []


class ConnectionFailingAgent:
    async def ainvoke(self, _state, config=None):
        raise RuntimeError("upstream connection detail must stay private")


@pytest.mark.anyio
async def test_agent_maps_unexpected_model_connection_failure_to_research_unavailable(
    caplog,
) -> None:
    researcher = ResearchAgent(
        settings(),
        model=object(),
        search_adapter=FakeSearchAdapter(),
        extract_adapter=FakeExtractAdapter(),
        agent_factory=lambda **_kwargs: ConnectionFailingAgent(),
        url_validator=lambda value: value,
    )

    with caplog.at_level("WARNING", logger="app.research.agent"):
        with pytest.raises(ResearchUnavailable, match="联网研究暂时不可用"):
            await researcher.research(
                QuizGenerateRequest(user_input="Harness Engineering 是什么")
            )

    assert "RuntimeError" in caplog.text
    assert "upstream connection detail" not in caplog.text
