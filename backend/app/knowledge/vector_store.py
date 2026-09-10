from __future__ import annotations

import hashlib
from pathlib import Path

import chromadb
from chromadb.errors import NotFoundError

from app.knowledge.chunking import KnowledgeChunk
from app.models.knowledge import RetrievedChunk


def collection_name_for_user(user_id: int) -> str:
    digest = hashlib.sha256(f"ai-learn-user:{user_id}".encode()).hexdigest()[:32]
    return f"user_{digest}"


class ChromaKnowledgeStore:
    def __init__(self, persist_dir: Path, client=None) -> None:
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or chromadb.PersistentClient(path=str(persist_dir))

    def _collection(self, user_id: int):
        return self.client.get_or_create_collection(
            name=collection_name_for_user(user_id), metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, user_id: int, chunks: list[KnowledgeChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("知识片段和向量数量不一致")
        if not chunks:
            return
        collection = self._collection(user_id)
        batch_size = min(getattr(self.client, "get_max_batch_size", lambda: 5000)(), 5000)
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            collection.upsert(
                ids=[item.chunk_id for item in batch],
                embeddings=embeddings[start : start + batch_size],
                documents=[item.content for item in batch],
                metadatas=[{
                    "user_id": user_id, "knowledge_base_id": item.knowledge_base_id,
                    "document_id": item.document_id, "filename": item.filename,
                    "chunk_index": item.chunk_index, "page": item.page or 0,
                    "section": item.section or "",
                } for item in batch],
            )

    def query(
        self, user_id: int, query_embedding: list[float], *, knowledge_base_ids: list[int], limit: int,
    ) -> list[RetrievedChunk]:
        if not knowledge_base_ids:
            return []
        try:
            collection = self.client.get_collection(collection_name_for_user(user_id))
        except NotFoundError:
            return []
        where = (
            {"knowledge_base_id": knowledge_base_ids[0]}
            if len(knowledge_base_ids) == 1
            else {"knowledge_base_id": {"$in": knowledge_base_ids}}
        )
        result = collection.query(
            query_embeddings=[query_embedding], n_results=limit, where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            RetrievedChunk(
                chunk_id=chunk_id, knowledge_base_id=metadata["knowledge_base_id"],
                document_id=metadata["document_id"], filename=metadata["filename"],
                content=content, score=max(0.0, min(1.0, 1.0 - float(distance))),
                chunk_index=metadata["chunk_index"], page=metadata.get("page") or None,
                section=metadata.get("section") or None,
            )
            for chunk_id, content, metadata, distance in zip(ids, documents, metadatas, distances)
        ]

    def delete_document(self, user_id: int, document_id: str) -> None:
        try:
            self.client.get_collection(collection_name_for_user(user_id)).delete(where={"document_id": document_id})
        except NotFoundError:
            return

    def delete_knowledge_base(self, user_id: int, knowledge_base_id: int) -> None:
        try:
            self.client.get_collection(collection_name_for_user(user_id)).delete(where={"knowledge_base_id": knowledge_base_id})
        except NotFoundError:
            return
