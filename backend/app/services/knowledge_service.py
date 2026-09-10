from __future__ import annotations

import asyncio
from uuid import uuid4

from app.models.knowledge import (
    DocumentIngestionTask,
    DocumentUploadAccepted,
    KnowledgeBaseCreate,
    KnowledgeBaseDetail,
    KnowledgeBaseUpdate,
    KnowledgeDocument,
)
from app.core.exceptions import EvidenceInsufficient


class KnowledgeNotFound(LookupError):
    pass


class KnowledgeService:
    def __init__(
        self, *, repository, file_store, vector_store, ingestion,
        knowledge_base_limit: int, document_limit: int,
    ) -> None:
        self.repository = repository
        self.file_store = file_store
        self.vector_store = vector_store
        self.ingestion = ingestion
        self.knowledge_base_limit = knowledge_base_limit
        self.document_limit = document_limit

    async def create(self, user_id: int, payload: KnowledgeBaseCreate):
        return await self.repository.create_knowledge_base(user_id, payload, limit=self.knowledge_base_limit)

    async def list(self, user_id: int):
        return await self.repository.list_knowledge_bases(user_id)

    async def validate_selection(self, user_id: int, knowledge_base_ids: list[int]) -> None:
        for knowledge_base_id in knowledge_base_ids:
            knowledge_base = await self.repository.get_knowledge_base(user_id, knowledge_base_id)
            if knowledge_base is None:
                raise KnowledgeNotFound("知识库不存在或无权访问")
            if knowledge_base.ready_document_count < 1:
                raise EvidenceInsufficient("所选知识库还没有可用于出题的文档")

    async def detail(self, user_id: int, knowledge_base_id: int) -> KnowledgeBaseDetail:
        summary = await self.repository.get_knowledge_base(user_id, knowledge_base_id)
        if summary is None:
            raise KnowledgeNotFound("知识库不存在")
        documents = await self.repository.list_documents(user_id, knowledge_base_id) or []
        return KnowledgeBaseDetail(**summary.model_dump(), documents=documents)

    async def update(self, user_id: int, knowledge_base_id: int, payload: KnowledgeBaseUpdate):
        result = await self.repository.update_knowledge_base(user_id, knowledge_base_id, payload)
        if result is None:
            raise KnowledgeNotFound("知识库不存在")
        return result

    async def delete(self, user_id: int, knowledge_base_id: int) -> None:
        documents = await self.repository.list_documents(user_id, knowledge_base_id)
        if documents is None:
            raise KnowledgeNotFound("知识库不存在")
        stored = []
        for item in documents:
            value = await self.repository.get_stored_document(user_id, item.document_id)
            if value:
                stored.append(value)
        await asyncio.to_thread(self.vector_store.delete_knowledge_base, user_id, knowledge_base_id)
        for item in stored:
            await asyncio.to_thread(self.file_store.delete, item.storage_key)
        deleted = await self.repository.delete_knowledge_base(user_id, knowledge_base_id)
        if deleted is None:
            raise KnowledgeNotFound("知识库不存在")

    async def upload(self, user_id: int, knowledge_base_id: int, upload) -> DocumentUploadAccepted:
        if await self.repository.get_knowledge_base(user_id, knowledge_base_id) is None:
            raise KnowledgeNotFound("知识库不存在")
        document_id = f"doc_{uuid4().hex}"
        task_id = f"ingest_{uuid4().hex}"
        stored = await self.file_store.save(upload, user_id=user_id, document_id=document_id)
        try:
            document, task = await self.repository.create_document_with_task(
                user_id=user_id, knowledge_base_id=knowledge_base_id,
                document_id=document_id, task_id=task_id, filename=stored.filename,
                content_type=stored.content_type, extension=stored.extension,
                size_bytes=stored.size_bytes, sha256=stored.sha256,
                storage_key=stored.storage_key, document_limit=self.document_limit,
            )
        except Exception:
            self.file_store.delete(stored.storage_key)
            raise
        self.ingestion.schedule(task_id)
        return DocumentUploadAccepted(document=document, task=task)

    async def list_documents(self, user_id: int, knowledge_base_id: int) -> list[KnowledgeDocument]:
        result = await self.repository.list_documents(user_id, knowledge_base_id)
        if result is None:
            raise KnowledgeNotFound("知识库不存在")
        return result

    async def document(self, user_id: int, knowledge_base_id: int, document_id: str) -> KnowledgeDocument:
        result = await self.repository.get_document(user_id, knowledge_base_id, document_id)
        if result is None:
            raise KnowledgeNotFound("文档不存在")
        return result

    async def delete_document(self, user_id: int, knowledge_base_id: int, document_id: str) -> None:
        stored = await self.repository.get_stored_document(user_id, document_id)
        if stored is None or stored.knowledge_base_id != knowledge_base_id:
            raise KnowledgeNotFound("文档不存在")
        await asyncio.to_thread(self.vector_store.delete_document, user_id, document_id)
        await asyncio.to_thread(self.file_store.delete, stored.storage_key)
        if await self.repository.delete_document(user_id, knowledge_base_id, document_id) is None:
            raise KnowledgeNotFound("文档不存在")

    async def reindex(self, user_id: int, knowledge_base_id: int, document_id: str) -> DocumentIngestionTask:
        task_id = f"ingest_{uuid4().hex}"
        await asyncio.to_thread(self.vector_store.delete_document, user_id, document_id)
        task = await self.repository.create_reindex_task(user_id, knowledge_base_id, document_id, task_id)
        if task is None:
            raise KnowledgeNotFound("文档不存在")
        self.ingestion.schedule(task_id)
        return task
