from __future__ import annotations

from datetime import datetime, timezone

from app.models.knowledge import RetrievedChunk
from app.research.models import EvidenceSource, ResearchBrief, ResearchFact, ResearchResult


def private_source_id(chunk: RetrievedChunk) -> str:
    return f"private_{chunk.document_id}_{chunk.chunk_index}"


def private_research_result(chunks: list[RetrievedChunk]) -> ResearchResult:
    sources = []
    facts = []
    for chunk in chunks:
        source_id = private_source_id(chunk)
        location = f"第 {chunk.page} 页" if chunk.page else chunk.section
        sources.append(
            EvidenceSource(
                source_id=source_id,
                title=chunk.filename,
                url="",
                site_name="私有知识库",
                acquisition_method="private_document",
                source_type="private_document",
                knowledge_base_id=chunk.knowledge_base_id,
                document_id=chunk.document_id,
                location=location,
                content=chunk.content,
                score=chunk.score,
            )
        )
        facts.append(ResearchFact(text=chunk.content[:1000], source_ids=[source_id]))
    filenames = list(dict.fromkeys(item.filename for item in chunks))
    return ResearchResult(
        grounding_mode="private",
        sources=sources,
        researched_at=datetime.now(timezone.utc),
        brief=ResearchBrief(
            resolved_topic="私有资料学习",
            domain="private knowledge",
            is_ambiguous=False,
            is_sufficient=bool(sources),
            summary=f"从 {len(filenames)} 份私有文档检索到 {len(sources)} 个相关片段。",
            key_facts=facts,
            first_party_source_ids=[item.source_id for item in sources],
        ),
    )


def combine_private_and_public(private: ResearchResult, public: ResearchResult | None) -> ResearchResult:
    if public is None or not public.sources:
        return private
    private_brief = private.brief
    public_brief = public.brief
    facts = (private_brief.key_facts if private_brief else []) + (public_brief.key_facts if public_brief else [])
    return ResearchResult(
        grounding_mode="hybrid",
        sources=[*private.sources, *public.sources],
        researched_at=public.researched_at or private.researched_at,
        brief=ResearchBrief(
            resolved_topic=(public_brief.resolved_topic if public_brief else "私有资料学习"),
            domain=(public_brief.domain if public_brief else "private knowledge"),
            is_ambiguous=False,
            is_sufficient=bool(private.sources),
            summary="；".join(filter(None, [private_brief.summary if private_brief else "", public_brief.summary if public_brief else ""])),
            key_facts=facts[:20],
            first_party_source_ids=(private_brief.first_party_source_ids if private_brief else [])[:8],
        ),
    )
