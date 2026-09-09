import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        deepseek_api_key="test-deepseek-key",
        jwt_secret="test-jwt-secret-that-is-at-least-32-chars",
        cors_origins=["http://localhost:10086"],
        **overrides,
    )


def test_research_defaults_are_bounded_and_disabled_without_opt_in() -> None:
    settings = make_settings()

    assert settings.web_research_enabled is False
    assert settings.research_max_tool_calls == 4
    assert settings.research_max_search_calls == 2
    assert settings.research_max_search_results == 8
    assert settings.research_max_extract_urls == 3
    assert settings.research_tool_timeout_seconds < settings.research_total_timeout_seconds


def test_enabled_research_requires_tavily_key() -> None:
    with pytest.raises(ValidationError, match="TAVILY_API_KEY"):
        make_settings(web_research_enabled=True, tavily_api_key="")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("research_total_timeout_seconds", 4),
        ("research_tool_timeout_seconds", 0),
        ("research_max_tool_calls", 9),
        ("research_max_search_calls", 5),
        ("research_max_search_results", 21),
        ("research_max_extract_urls", 11),
        ("research_max_evidence_chars", 3999),
    ],
)
def test_research_config_rejects_values_outside_safe_bounds(
    field: str, value: int
) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


def test_tool_timeout_must_fit_inside_total_budget() -> None:
    with pytest.raises(ValidationError, match="研究工具超时必须小于研究总超时"):
        make_settings(
            research_total_timeout_seconds=20,
            research_tool_timeout_seconds=20,
        )
