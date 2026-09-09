import pytest

from app.core.exceptions import EvidenceInsufficient, TopicAmbiguous
from app.research.evidence import (
    EvidenceCollector,
    restrict_brief_to_known_sources,
    validate_research_brief,
)
from app.research.models import ResearchBrief, ResearchFact


def test_collector_normalizes_deduplicates_and_prefers_extracted_content() -> None:
    collector = EvidenceCollector(max_total_chars=500, max_source_chars=300)
    search_sources = collector.add_search(
        {
            "results": [
                {
                    "title": "Official guide",
                    "url": "https://Example.com/guide#intro",
                    "content": "short snippet",
                    "score": 0.9,
                },
                {
                    "title": "Duplicate",
                    "url": "https://example.com/guide",
                    "content": "duplicate snippet",
                    "score": 0.8,
                },
            ]
        }
    )
    extracted = collector.add_extract(
        {
            "results": [
                {
                    "url": "https://example.com/guide",
                    "raw_content": "full official page " * 30,
                }
            ]
        },
        user_urls=set(),
    )

    assert len(search_sources) == 1
    assert len(extracted) == 1
    assert len(collector.sources) == 1
    source = collector.sources[0]
    assert source.title == "Official guide"
    assert source.site_name == "example.com"
    assert source.acquisition_method == "search_result_extract"
    assert source.content.startswith("full official page")
    assert len(source.content) <= 300


def test_collector_marks_user_url_and_enforces_total_budget() -> None:
    collector = EvidenceCollector(max_total_chars=20, max_source_chars=20)
    sources = collector.add_extract(
        {
            "results": [
                {"url": "https://example.com/a", "raw_content": "A" * 15},
                {"url": "https://example.org/b", "raw_content": "B" * 15},
            ]
        },
        user_urls={"https://example.com/a"},
    )

    assert sum(len(item.content) for item in sources) == 20
    assert sources[0].acquisition_method == "user_url_extract"
    assert sources[1].acquisition_method == "search_result_extract"


def test_public_source_does_not_expose_captured_content() -> None:
    collector = EvidenceCollector(max_total_chars=100, max_source_chars=100)
    source = collector.add_search(
        {
            "results": [
                {
                    "title": "Guide",
                    "url": "https://example.com/guide",
                    "content": "private captured content",
                }
            ]
        }
    )[0]

    assert "content" not in source.to_public().model_dump()


def test_private_literal_search_result_is_not_evidence() -> None:
    collector = EvidenceCollector(max_total_chars=100)

    assert collector.add_search(
        {
            "results": [
                {
                    "title": "Internal",
                    "url": "http://127.0.0.1/admin",
                    "content": "secret",
                }
            ]
        }
    ) == []


def test_one_declared_first_party_source_is_sufficient() -> None:
    collector = EvidenceCollector(max_total_chars=100)
    source = collector.add_search(
        {
            "results": [
                {
                    "title": "Official guide",
                    "url": "https://example.com/guide",
                    "content": "supported fact",
                }
            ]
        }
    )[0]
    brief = ResearchBrief(
        resolved_topic="Topic",
        domain="software",
        is_ambiguous=False,
        is_sufficient=True,
        summary="Enough evidence",
        key_facts=[ResearchFact(text="fact", source_ids=[source.source_id])],
        first_party_source_ids=[source.source_id],
    )

    validate_research_brief(brief, collector.sources)


def test_two_independent_sites_are_sufficient() -> None:
    collector = EvidenceCollector(max_total_chars=200)
    sources = collector.add_search(
        {
            "results": [
                {"title": "A", "url": "https://a.example/guide", "content": "fact"},
                {"title": "B", "url": "https://b.example/guide", "content": "fact"},
            ]
        }
    )
    brief = ResearchBrief(
        resolved_topic="Topic",
        domain="software",
        is_ambiguous=False,
        is_sufficient=True,
        summary="Enough evidence",
        key_facts=[
            ResearchFact(text="fact", source_ids=[item.source_id for item in sources])
        ],
    )

    validate_research_brief(brief, collector.sources)


def test_unknown_source_and_ambiguity_are_rejected() -> None:
    brief = ResearchBrief(
        resolved_topic="Topic",
        domain="unknown",
        is_ambiguous=True,
        is_sufficient=False,
        summary="Ambiguous",
        key_facts=[ResearchFact(text="fact", source_ids=["src_unknown"])],
    )

    with pytest.raises(TopicAmbiguous):
        validate_research_brief(brief, [])

    unambiguous = brief.model_copy(update={"is_ambiguous": False, "is_sufficient": True})
    with pytest.raises(EvidenceInsufficient):
        validate_research_brief(unambiguous, [])


def test_brief_restriction_removes_hallucinated_source_references() -> None:
    collector = EvidenceCollector(max_total_chars=200)
    sources = collector.add_search(
        {
            "results": [
                {"title": "A", "url": "https://a.example/", "content": "fact"},
                {"title": "B", "url": "https://b.example/", "content": "fact"},
            ]
        }
    )
    brief = ResearchBrief(
        resolved_topic="Topic",
        domain="software",
        is_ambiguous=False,
        is_sufficient=True,
        summary="Enough evidence",
        key_facts=[
            ResearchFact(
                text="supported",
                source_ids=[sources[0].source_id, "src_hallucinated"],
            ),
            ResearchFact(text="unsupported", source_ids=["src_hallucinated"]),
        ],
        first_party_source_ids=[sources[1].source_id, "src_hallucinated"],
    )

    restricted = restrict_brief_to_known_sources(brief, sources)

    assert len(restricted.key_facts) == 1
    assert restricted.key_facts[0].source_ids == [sources[0].source_id]
    assert restricted.first_party_source_ids == [sources[1].source_id]
