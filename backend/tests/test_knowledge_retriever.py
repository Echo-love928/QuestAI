import pytest

from app.knowledge.retriever import KnowledgeRetriever, PrivateEvidenceInsufficient
from app.models.knowledge import RetrievedChunk


class FakeEmbedding:
    async def embed_query(self, text: str) -> list[float]:
        assert text == "退款流程"
        return [1.0, 0.0]


class FakeStore:
    def query(self, user_id, query_embedding, *, knowledge_base_ids, limit):
        assert user_id == 7 and knowledge_base_ids == [10]
        return [
            RetrievedChunk(chunk_id="1", knowledge_base_id=10, document_id="a", filename="a.pdf", content="A" * 80, score=.9, chunk_index=0),
            RetrievedChunk(chunk_id="2", knowledge_base_id=10, document_id="a", filename="a.pdf", content="B" * 80, score=.8, chunk_index=1),
            RetrievedChunk(chunk_id="3", knowledge_base_id=10, document_id="b", filename="b.md", content="C" * 80, score=.7, chunk_index=0),
        ][:limit]


@pytest.mark.anyio
async def test_retriever_applies_score_and_per_document_limit() -> None:
    retriever = KnowledgeRetriever(FakeEmbedding(), FakeStore(), top_k=8, min_score=.75, max_per_document=1, min_total_chars=50)
    chunks = await retriever.retrieve(user_id=7, knowledge_base_ids=[10], query="退款流程")
    assert [item.chunk_id for item in chunks] == ["1"]


@pytest.mark.anyio
async def test_retriever_fails_when_private_evidence_is_insufficient() -> None:
    retriever = KnowledgeRetriever(FakeEmbedding(), FakeStore(), top_k=1, min_score=.95, max_per_document=2, min_total_chars=100)
    with pytest.raises(PrivateEvidenceInsufficient):
        await retriever.retrieve(user_id=7, knowledge_base_ids=[10], query="退款流程")
