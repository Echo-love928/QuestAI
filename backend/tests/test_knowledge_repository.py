import os

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.db.knowledge_repository import KnowledgeRepository, KnowledgeQuotaExceeded
from app.models.knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate


@pytest.fixture
async def repository():
    if os.getenv("RUN_MYSQL_TESTS") != "1":
        pytest.skip("设置 RUN_MYSQL_TESTS=1 后运行 MySQL 集成测试")
    configured = Settings()
    settings = Settings(
        _env_file=None,
        mysql_host=os.getenv("TEST_MYSQL_HOST", configured.mysql_host),
        mysql_port=int(os.getenv("TEST_MYSQL_PORT", "3306")),
        mysql_user=os.getenv("TEST_MYSQL_USER", configured.mysql_user),
        mysql_password=os.getenv("TEST_MYSQL_PASSWORD", configured.mysql_password),
        mysql_database="AI-learn-test",
    )
    database = Database(settings)
    await database.connect()
    async with database.require_pool().acquire() as connection:
        async with connection.cursor() as cursor:
            for table in ("document_ingestion_tasks", "knowledge_documents", "knowledge_bases", "users"):
                await cursor.execute(f"DELETE FROM `{table}`")
            await cursor.execute("INSERT INTO users (openid) VALUES ('kb-owner'), ('kb-stranger')")
        await connection.commit()
    rows = await database.fetch_one("SELECT MIN(id) AS id FROM users")
    assert rows
    try:
        yield KnowledgeRepository(database), int(rows["id"]), int(rows["id"]) + 1
    finally:
        async with database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                for table in ("document_ingestion_tasks", "knowledge_documents", "knowledge_bases", "users"):
                    await cursor.execute(f"DELETE FROM `{table}`")
            await connection.commit()
        await database.close()


@pytest.mark.anyio
async def test_crud_is_scoped_to_owner(repository) -> None:
    repo, owner_id, stranger_id = repository
    created = await repo.create_knowledge_base(owner_id, KnowledgeBaseCreate(name="客服资料"), limit=5)
    assert created.name == "客服资料"
    assert await repo.get_knowledge_base(stranger_id, created.id) is None

    updated = await repo.update_knowledge_base(owner_id, created.id, KnowledgeBaseUpdate(description="内部培训"))
    assert updated is not None and updated.description == "内部培训"
    assert len(await repo.list_knowledge_bases(owner_id)) == 1
    assert await repo.delete_knowledge_base(stranger_id, created.id) is None
    assert await repo.delete_knowledge_base(owner_id, created.id) == []


@pytest.mark.anyio
async def test_knowledge_base_quota_is_enforced(repository) -> None:
    repo, owner_id, _ = repository
    await repo.create_knowledge_base(owner_id, KnowledgeBaseCreate(name="一号"), limit=1)
    with pytest.raises(KnowledgeQuotaExceeded):
        await repo.create_knowledge_base(owner_id, KnowledgeBaseCreate(name="二号"), limit=1)


@pytest.mark.anyio
async def test_document_task_state_machine_and_retry_are_persistent(repository) -> None:
    repo, owner_id, stranger_id = repository
    kb = await repo.create_knowledge_base(owner_id, KnowledgeBaseCreate(name="制度"), limit=5)
    document, task = await repo.create_document_with_task(
        user_id=owner_id,
        knowledge_base_id=kb.id,
        document_id="doc_test",
        task_id="ingest_test",
        filename="制度.md",
        content_type="text/markdown",
        extension="md",
        size_bytes=16,
        sha256="a" * 64,
        storage_key="safe/doc_test/制度.md",
        document_limit=20,
    )
    assert document.status == "uploaded"
    assert task.status == "pending"
    assert await repo.get_stored_document(stranger_id, "doc_test") is None

    claimed = await repo.claim_ingestion_task("ingest_test")
    assert claimed is not None and claimed.status == "processing"
    assert await repo.claim_ingestion_task("ingest_test") is None
    await repo.update_ingestion_stage("ingest_test", "parsing")
    await repo.complete_ingestion_task("ingest_test", chunk_count=3, model="text-embedding-v4", dimensions=1024)
    ready = await repo.get_document(owner_id, kb.id, "doc_test")
    assert ready is not None and ready.status == "ready" and ready.chunk_count == 3

    retry = await repo.create_reindex_task(owner_id, kb.id, "doc_test", "ingest_retry")
    assert retry is not None and retry.attempt == 2 and retry.status == "pending"


@pytest.mark.anyio
async def test_failed_and_interrupted_tasks_can_be_recovered(repository) -> None:
    repo, owner_id, _ = repository
    kb = await repo.create_knowledge_base(owner_id, KnowledgeBaseCreate(name="恢复测试"), limit=5)
    await repo.create_document_with_task(
        user_id=owner_id, knowledge_base_id=kb.id, document_id="doc_recover",
        task_id="ingest_recover", filename="恢复.md", content_type="text/markdown",
        extension="md", size_bytes=10, sha256="b" * 64,
        storage_key="safe/doc_recover/恢复.md", document_limit=20,
    )
    assert await repo.claim_ingestion_task("ingest_recover") is not None
    pending = await repo.recover_interrupted_tasks()
    assert "ingest_recover" in pending

    assert await repo.claim_ingestion_task("ingest_recover") is not None
    await repo.fail_ingestion_task("ingest_recover", code="PARSER_FAILED", message="无法解析")
    failed = await repo.get_document(owner_id, kb.id, "doc_recover")
    assert failed is not None and failed.status == "failed"
    assert failed.error_code == "PARSER_FAILED"
