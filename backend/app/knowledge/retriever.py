from __future__ import annotations

from collections import defaultdict

from app.knowledge.embeddings import EmbeddingGateway
from app.knowledge.vector_store import ChromaKnowledgeStore
from app.models.knowledge import RetrievedChunk
from app.core.exceptions import EvidenceInsufficient


class PrivateEvidenceInsufficient(EvidenceInsufficient):
    pass


class KnowledgeRetriever:
    def __init__(
        self, embedding: EmbeddingGateway, store: ChromaKnowledgeStore, *, top_k: int,
        min_score: float, max_per_document: int, min_total_chars: int = 80,
    ) -> None:
        self.embedding = embedding
        self.store = store
        self.top_k = top_k
        self.min_score = min_score
        self.max_per_document = max_per_document
        self.min_total_chars = min_total_chars

    async def retrieve(self, *, user_id: int, knowledge_base_ids: list[int], query: str) -> list[RetrievedChunk]:
        if not knowledge_base_ids:
            raise PrivateEvidenceInsufficient("未选择知识库")
        vector = await self.embedding.embed_query(query)
        candidates = self.store.query(
            user_id, vector, knowledge_base_ids=knowledge_base_ids,
            limit=self.top_k * max(1, len(knowledge_base_ids)),
        )
        per_document: dict[str, int] = defaultdict(int)
        accepted = []
        for item in candidates:
            if item.score < self.min_score or per_document[item.document_id] >= self.max_per_document:
                continue
            accepted.append(item)
            per_document[item.document_id] += 1
        if sum(len(item.content) for item in accepted) < self.min_total_chars:
            raise PrivateEvidenceInsufficient("私有资料不足以支持出题")
        return accepted
