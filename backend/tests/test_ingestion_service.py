from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.knowledge.chunking import DocumentChunker
from app.knowledge.ingestion import IngestionService
from app.knowledge.parsers import DocumentParseError
from app.models.knowledge import DocumentIngestionTask, StoredDocument


class FakeRepository:
    def __init__(self) -> None:
        self.claimed = False
        self.stages = []
        self.completed = None
        self.failed = None

    async def claim_ingestion_task(self, task_id):
        if self.claimed:
            return None
        self.claimed = True
        return DocumentIngestionTask(task_id=task_id, document_id="doc", status="processing", stage="uploaded")

    async def get_stored_document_for_task(self, task_id):
        return StoredDocument(
            document_id="doc", knowledge_base_id=2, user_id=7, filename="guide.md",
            content_type="text/markdown", extension="md", size_bytes=20,
            sha256="a" * 64, storage_key="u/doc/guide.md", status="uploaded",
        )

    async def update_ingestion_stage(self, task_id, stage):
        self.stages.append(stage)

    async def complete_ingestion_task(self, task_id, **kwargs):
        self.completed = kwargs

    async def fail_ingestion_task(self, task_id, **kwargs):
        self.failed = kwargs

    async def recover_interrupted_tasks(self):
        return ["recover-one"]


class FakeFiles:
    def resolve(self, key):
        return Path("guide.md")


class FakeParser:
    async def parse(self, path, extension):
        return [Document(page_content="客服处理流程。" * 20, metadata={"page": 1})]


class FailingParser:
    async def parse(self, path, extension):
        raise DocumentParseError("扫描 PDF 暂不支持 OCR")


class FakeEmbedding:
    async def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FakeStore:
    def __init__(self):
        self.deleted = []
        self.upserted = None

    def delete_document(self, user_id, document_id):
        self.deleted.append((user_id, document_id))

    def upsert(self, user_id, chunks, embeddings):
        self.upserted = (user_id, chunks, embeddings)


@pytest.mark.anyio
async def test_ingestion_pipeline_updates_all_stages_and_completes() -> None:
    repo, store = FakeRepository(), FakeStore()
    service = IngestionService(
        repository=repo, files=FakeFiles(), parser=FakeParser(),
        chunker=DocumentChunker(chunk_size=50, chunk_overlap=5, max_chunks=100),
        embedding=FakeEmbedding(), store=store, embedding_model="text-embedding-v4", embedding_dimensions=2,
    )
    assert await service.process("task") is True
    assert repo.stages == ["parsing", "chunking", "embedding"]
    assert repo.completed["chunk_count"] > 0
    assert store.deleted == [(7, "doc")]
    assert store.upserted[0] == 7


@pytest.mark.anyio
async def test_ingestion_failure_is_persisted_without_raising() -> None:
    repo = FakeRepository()
    service = IngestionService(
        repository=repo, files=FakeFiles(), parser=FailingParser(),
        chunker=DocumentChunker(chunk_size=50, chunk_overlap=5, max_chunks=100),
        embedding=FakeEmbedding(), store=FakeStore(), embedding_model="m", embedding_dimensions=2,
    )
    assert await service.process("task") is False
    assert repo.failed["code"] == "DOCUMENT_PARSE_FAILED"
    assert "扫描" in repo.failed["message"]


@pytest.mark.anyio
async def test_duplicate_task_claim_is_ignored() -> None:
    repo = FakeRepository()
    repo.claimed = True
    service = IngestionService(
        repository=repo, files=FakeFiles(), parser=FakeParser(),
        chunker=DocumentChunker(chunk_size=50, chunk_overlap=5, max_chunks=100),
        embedding=FakeEmbedding(), store=FakeStore(), embedding_model="m", embedding_dimensions=2,
    )
    assert await service.process("task") is False
