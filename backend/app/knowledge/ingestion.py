from __future__ import annotations

import asyncio
import logging

from app.knowledge.embeddings import EmbeddingError, EmbeddingGateway
from app.knowledge.parsers import DocumentParseError


logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self, *, repository, files, parser, chunker, embedding: EmbeddingGateway,
        store, embedding_model: str, embedding_dimensions: int,
    ) -> None:
        self.repository = repository
        self.files = files
        self.parser = parser
        self.chunker = chunker
        self.embedding = embedding
        self.store = store
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self._running: set[asyncio.Task] = set()

    def schedule(self, task_id: str) -> None:
        task = asyncio.create_task(self.process(task_id), name=f"ingest:{task_id}")
        self._running.add(task)
        task.add_done_callback(self._running.discard)

    async def recover(self) -> int:
        task_ids = await self.repository.recover_interrupted_tasks()
        for task_id in task_ids:
            self.schedule(task_id)
        return len(task_ids)

    async def process(self, task_id: str) -> bool:
        task = await self.repository.claim_ingestion_task(task_id)
        if task is None:
            return False
        try:
            document = await self.repository.get_stored_document_for_task(task_id)
            if document is None:
                raise LookupError("文档记录不存在")
            path = self.files.resolve(document.storage_key)
            await self.repository.update_ingestion_stage(task_id, "parsing")
            pages = await self.parser.parse(path, document.extension)
            await self.repository.update_ingestion_stage(task_id, "chunking")
            chunks = self.chunker.split(
                pages, knowledge_base_id=document.knowledge_base_id,
                document_id=document.document_id, filename=document.filename,
                index_version=document.index_version,
            )
            await self.repository.update_ingestion_stage(task_id, "embedding")
            vectors = await self.embedding.embed_documents([item.content for item in chunks])
            await asyncio.to_thread(self.store.delete_document, document.user_id, document.document_id)
            await asyncio.to_thread(self.store.upsert, document.user_id, chunks, vectors)
            await self.repository.complete_ingestion_task(
                task_id, chunk_count=len(chunks), model=self.embedding_model,
                dimensions=self.embedding_dimensions,
            )
            return True
        except DocumentParseError as exc:
            await self.repository.fail_ingestion_task(
                task_id, code="DOCUMENT_PARSE_FAILED", message=str(exc)
            )
        except EmbeddingError:
            await self.repository.fail_ingestion_task(
                task_id, code="EMBEDDING_UNAVAILABLE", message="向量服务暂时不可用，请稍后重试"
            )
        except (ValueError, LookupError) as exc:
            await self.repository.fail_ingestion_task(
                task_id, code="DOCUMENT_PROCESSING_FAILED", message=str(exc)
            )
        except Exception:
            logger.exception("knowledge ingestion failed task_id=%s", task_id)
            await self.repository.fail_ingestion_task(
                task_id, code="DOCUMENT_PROCESSING_FAILED", message="资料处理失败，请稍后重试"
            )
        return False
