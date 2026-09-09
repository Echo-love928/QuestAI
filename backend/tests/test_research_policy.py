import socket

import pytest

from app.models.quiz import QuizGenerateRequest
from app.research.policy import InputKind, classify_input, localize_query
from app.research.safety import UnsafeUrlError, validate_public_url


def test_classifies_short_topic_as_research_required() -> None:
    decision = classify_input(
        QuizGenerateRequest(user_input="Harness Engineering 是什么"),
        full_material_min_chars=300,
    )

    assert decision.kind == InputKind.TOPIC
    assert decision.requires_research is True


def test_classifies_complete_material_without_forced_research() -> None:
    material = "这是一段完整学习资料。" * 40
    decision = classify_input(
        QuizGenerateRequest(user_input=material), full_material_min_chars=300
    )

    assert decision.kind == InputKind.MATERIAL
    assert decision.requires_research is False


def test_temporal_material_still_requires_research() -> None:
    material = ("这是一段完整学习资料。" * 40) + "请按最新版本出题"
    decision = classify_input(
        QuizGenerateRequest(user_input=material), full_material_min_chars=300
    )

    assert decision.kind == InputKind.MATERIAL
    assert decision.requires_research is True


def test_explicit_url_input_is_extracted() -> None:
    decision = classify_input(
        QuizGenerateRequest(
            user_input="https://docs.example.com/new-topic", source_type="url"
        ),
        full_material_min_chars=300,
    )

    assert decision.kind == InputKind.URL
    assert decision.urls == ["https://docs.example.com/new-topic"]
    assert decision.requires_research is True


def test_text_with_url_and_instruction_is_mixed() -> None:
    decision = classify_input(
        QuizGenerateRequest(
            user_input="请结合 https://example.com/spec 讲解最新变化"
        ),
        full_material_min_chars=300,
    )

    assert decision.kind == InputKind.MIXED
    assert decision.urls == ["https://example.com/spec"]


def test_localize_query_preserves_original_and_adds_context() -> None:
    query = localize_query(
        "驾驭工程",
        english_term="Harness Engineering",
        city="上海",
        country="中国",
    )

    assert query == "驾驭工程 Harness Engineering 上海 中国"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "http://user:pass@example.com/secret",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.8/internal",
        "http://[::1]/admin",
    ],
)
def test_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_url(url, resolver=lambda *_: [])


def test_accepts_public_https_url_with_public_dns() -> None:
    def resolver(*_):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    assert (
        validate_public_url("https://Example.com/docs#part", resolver=resolver)
        == "https://example.com/docs"
    )


def test_accepts_proxy_fake_ip_for_non_local_hostname() -> None:
    def resolver(*_):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.18.0.159", 443))]

    assert (
        validate_public_url("https://docs.langchain.com/guide", resolver=resolver)
        == "https://docs.langchain.com/guide"
    )
