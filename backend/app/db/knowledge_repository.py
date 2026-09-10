from __future__ import annotations

from typing import Any

import aiomysql

from app.db.database import Database
from app.models.knowledge import (
    DocumentIngestionTask,
    IngestionStage,
    KnowledgeBaseCreate,
    KnowledgeBaseSummary,
    KnowledgeBaseUpdate,
    KnowledgeDocument,
    StoredDocument,
)


class KnowledgeQuotaExceeded(ValueError):
    pass


def _summary(row: dict[str, Any]) -> KnowledgeBaseSummary:
    return KnowledgeBaseSummary(
        id=row["id"], name=row["name"], description=row.get("description"),
        document_count=int(row.get("document_count") or 0),
        ready_document_count=int(row.get("ready_document_count") or 0),
        chunk_count=int(row.get("chunk_count") or 0),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _document(row: dict[str, Any]) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id=row["document_id"], knowledge_base_id=row["knowledge_base_id"],
        filename=row["filename"], content_type=row["content_type"], size_bytes=row["size_bytes"],
        status=row["status"], error_code=row.get("error_code"), error_message=row.get("error_message"),
        chunk_count=row.get("chunk_count") or 0, embedding_model=row.get("embedding_model"),
        embedding_dimensions=row.get("embedding_dimensions"), index_version=row.get("index_version") or 1,
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _task(row: dict[str, Any]) -> DocumentIngestionTask:
    return DocumentIngestionTask(
        task_id=row["task_id"], document_id=row["document_id"], status=row["status"],
        stage=row["stage"], attempt=row.get("attempt") or 1, error_code=row.get("error_code"),
        error_message=row.get("error_message"), created_at=row.get("created_at"), updated_at=row.get("updated_at"),
    )


class KnowledgeRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_knowledge_base(self, user_id: int, request: KnowledgeBaseCreate, *, limit: int) -> KnowledgeBaseSummary:
        async with self.database.require_pool().acquire() as connection:
            try:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
                    await cursor.fetchone()
                    await cursor.execute("SELECT COUNT(*) AS total FROM knowledge_bases WHERE user_id = %s", (user_id,))
                    count = await cursor.fetchone()
                    if int(count["total"]) >= limit:
                        raise KnowledgeQuotaExceeded(f"每位用户最多创建 {limit} 个知识库")
                    await cursor.execute(
                        "INSERT INTO knowledge_bases (user_id, name, description) VALUES (%s, %s, %s)",
                        (user_id, request.name, request.description),
                    )
                    knowledge_base_id = cursor.lastrowid
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
        result = await self.get_knowledge_base(user_id, knowledge_base_id)
        if result is None:
            raise RuntimeError("知识库创建失败")
        return result

    async def list_knowledge_bases(self, user_id: int) -> list[KnowledgeBaseSummary]:
        rows = await self.database.fetch_all(
            """
            SELECT kb.id, kb.name, kb.description, kb.created_at, kb.updated_at,
                   COUNT(d.id) AS document_count,
                   COALESCE(SUM(d.status = 'ready'), 0) AS ready_document_count,
                   COALESCE(SUM(d.chunk_count), 0) AS chunk_count
            FROM knowledge_bases kb
            LEFT JOIN knowledge_documents d ON d.knowledge_base_id = kb.id
            WHERE kb.user_id = %s GROUP BY kb.id ORDER BY kb.updated_at DESC
            """, (user_id,),
        )
        return [_summary(row) for row in rows]

    async def get_knowledge_base(self, user_id: int, knowledge_base_id: int) -> KnowledgeBaseSummary | None:
        row = await self.database.fetch_one(
            """
            SELECT kb.id, kb.name, kb.description, kb.created_at, kb.updated_at,
                   COUNT(d.id) AS document_count,
                   COALESCE(SUM(d.status = 'ready'), 0) AS ready_document_count,
                   COALESCE(SUM(d.chunk_count), 0) AS chunk_count
            FROM knowledge_bases kb
            LEFT JOIN knowledge_documents d ON d.knowledge_base_id = kb.id
            WHERE kb.user_id = %s AND kb.id = %s GROUP BY kb.id
            """, (user_id, knowledge_base_id),
        )
        return _summary(row) if row else None

    async def update_knowledge_base(self, user_id: int, knowledge_base_id: int, update: KnowledgeBaseUpdate) -> KnowledgeBaseSummary | None:
        changes = update.model_dump(exclude_unset=True)
        assignments = ", ".join(f"{key} = %s" for key in changes)
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"UPDATE knowledge_bases SET {assignments} WHERE id = %s AND user_id = %s",
                    (*changes.values(), knowledge_base_id, user_id),
                )
                changed = cursor.rowcount
            await connection.commit()
        return await self.get_knowledge_base(user_id, knowledge_base_id) if changed else None

    async def delete_knowledge_base(self, user_id: int, knowledge_base_id: int) -> list[StoredDocument] | None:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM knowledge_documents WHERE user_id = %s AND knowledge_base_id = %s",
                    (user_id, knowledge_base_id),
                )
                rows = await cursor.fetchall()
                await cursor.execute(
                    "DELETE FROM knowledge_bases WHERE id = %s AND user_id = %s", (knowledge_base_id, user_id)
                )
                changed = cursor.rowcount
            await connection.commit()
        if not changed:
            return None
        return [StoredDocument.model_validate(row) for row in rows]

    async def create_document_with_task(
        self, *, user_id: int, knowledge_base_id: int, document_id: str, task_id: str,
        filename: str, content_type: str, extension: str, size_bytes: int, sha256: str,
        storage_key: str, document_limit: int,
    ) -> tuple[KnowledgeDocument, DocumentIngestionTask]:
        async with self.database.require_pool().acquire() as connection:
            try:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        "SELECT id FROM knowledge_bases WHERE id = %s AND user_id = %s FOR UPDATE",
                        (knowledge_base_id, user_id),
                    )
                    if await cursor.fetchone() is None:
                        raise LookupError("知识库不存在")
                    await cursor.execute("SELECT COUNT(*) AS total FROM knowledge_documents WHERE knowledge_base_id = %s", (knowledge_base_id,))
                    count = await cursor.fetchone()
                    if int(count["total"]) >= document_limit:
                        raise KnowledgeQuotaExceeded(f"每个知识库最多保存 {document_limit} 份文档")
                    await cursor.execute(
                        """INSERT INTO knowledge_documents
                        (document_id, knowledge_base_id, user_id, filename, content_type, extension,
                         size_bytes, sha256, storage_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (document_id, knowledge_base_id, user_id, filename, content_type, extension, size_bytes, sha256, storage_key),
                    )
                    await cursor.execute(
                        """INSERT INTO document_ingestion_tasks
                        (task_id, document_id, knowledge_base_id, user_id) VALUES (%s,%s,%s,%s)""",
                        (task_id, document_id, knowledge_base_id, user_id),
                    )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
        document = await self.get_document(user_id, knowledge_base_id, document_id)
        task = await self.get_ingestion_task(user_id, task_id)
        if document is None or task is None:
            raise RuntimeError("文档任务创建失败")
        return document, task

    async def list_documents(self, user_id: int, knowledge_base_id: int) -> list[KnowledgeDocument] | None:
        if await self.get_knowledge_base(user_id, knowledge_base_id) is None:
            return None
        rows = await self.database.fetch_all(
            "SELECT * FROM knowledge_documents WHERE user_id = %s AND knowledge_base_id = %s ORDER BY created_at DESC",
            (user_id, knowledge_base_id),
        )
        return [_document(row) for row in rows]

    async def get_document(self, user_id: int, knowledge_base_id: int, document_id: str) -> KnowledgeDocument | None:
        row = await self.database.fetch_one(
            "SELECT * FROM knowledge_documents WHERE user_id = %s AND knowledge_base_id = %s AND document_id = %s",
            (user_id, knowledge_base_id, document_id),
        )
        return _document(row) if row else None

    async def get_stored_document(self, user_id: int, document_id: str) -> StoredDocument | None:
        row = await self.database.fetch_one(
            "SELECT * FROM knowledge_documents WHERE user_id = %s AND document_id = %s", (user_id, document_id)
        )
        return StoredDocument.model_validate(row) if row else None

    async def delete_document(self, user_id: int, knowledge_base_id: int, document_id: str) -> StoredDocument | None:
        document = await self.get_stored_document(user_id, document_id)
        if document is None or document.knowledge_base_id != knowledge_base_id:
            return None
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM knowledge_documents WHERE user_id=%s AND knowledge_base_id=%s AND document_id=%s",
                    (user_id, knowledge_base_id, document_id),
                )
                changed = cursor.rowcount
            await connection.commit()
        return document if changed else None

    async def get_stored_document_for_task(self, task_id: str) -> StoredDocument | None:
        row = await self.database.fetch_one(
            """SELECT d.* FROM knowledge_documents d
            JOIN document_ingestion_tasks t ON t.document_id=d.document_id
            WHERE t.task_id=%s""", (task_id,)
        )
        return StoredDocument.model_validate(row) if row else None

    async def get_ingestion_task(self, user_id: int, task_id: str) -> DocumentIngestionTask | None:
        row = await self.database.fetch_one(
            "SELECT * FROM document_ingestion_tasks WHERE user_id = %s AND task_id = %s", (user_id, task_id)
        )
        return _task(row) if row else None

    async def claim_ingestion_task(self, task_id: str) -> DocumentIngestionTask | None:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """UPDATE document_ingestion_tasks SET status='processing', started_at=CURRENT_TIMESTAMP(3)
                    WHERE task_id=%s AND status='pending'""", (task_id,),
                )
                if cursor.rowcount == 0:
                    await connection.rollback()
                    return None
                await cursor.execute("SELECT * FROM document_ingestion_tasks WHERE task_id=%s", (task_id,))
                row = await cursor.fetchone()
            await connection.commit()
        return _task(row)

    async def update_ingestion_stage(self, task_id: str, stage: IngestionStage) -> None:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("UPDATE document_ingestion_tasks SET stage=%s WHERE task_id=%s", (stage, task_id))
                await cursor.execute(
                    """UPDATE knowledge_documents d JOIN document_ingestion_tasks t ON t.document_id=d.document_id
                    SET d.status=%s, d.error_code=NULL, d.error_message=NULL WHERE t.task_id=%s""", (stage, task_id)
                )
            await connection.commit()

    async def complete_ingestion_task(self, task_id: str, *, chunk_count: int, model: str, dimensions: int) -> None:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """UPDATE document_ingestion_tasks SET status='completed', stage='ready', completed_at=CURRENT_TIMESTAMP(3)
                    WHERE task_id=%s""", (task_id,),
                )
                await cursor.execute(
                    """UPDATE knowledge_documents d JOIN document_ingestion_tasks t ON t.document_id=d.document_id
                    SET d.status='ready', d.chunk_count=%s, d.embedding_model=%s, d.embedding_dimensions=%s,
                        d.error_code=NULL, d.error_message=NULL WHERE t.task_id=%s""",
                    (chunk_count, model, dimensions, task_id),
                )
            await connection.commit()

    async def fail_ingestion_task(self, task_id: str, *, code: str, message: str) -> None:
        safe_message = message[:255]
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """UPDATE document_ingestion_tasks SET status='failed', stage='failed', error_code=%s,
                    error_message=%s, completed_at=CURRENT_TIMESTAMP(3) WHERE task_id=%s""", (code, safe_message, task_id)
                )
                await cursor.execute(
                    """UPDATE knowledge_documents d JOIN document_ingestion_tasks t ON t.document_id=d.document_id
                    SET d.status='failed', d.error_code=%s, d.error_message=%s WHERE t.task_id=%s""",
                    (code, safe_message, task_id),
                )
            await connection.commit()

    async def create_reindex_task(self, user_id: int, knowledge_base_id: int, document_id: str, task_id: str) -> DocumentIngestionTask | None:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT MAX(attempt) AS attempt FROM document_ingestion_tasks WHERE user_id=%s AND knowledge_base_id=%s AND document_id=%s",
                    (user_id, knowledge_base_id, document_id),
                )
                row = await cursor.fetchone()
                await cursor.execute(
                    "SELECT document_id FROM knowledge_documents WHERE user_id=%s AND knowledge_base_id=%s AND document_id=%s FOR UPDATE",
                    (user_id, knowledge_base_id, document_id),
                )
                if await cursor.fetchone() is None:
                    await connection.rollback()
                    return None
                attempt = int(row["attempt"] or 0) + 1
                await cursor.execute(
                    """INSERT INTO document_ingestion_tasks
                    (task_id, document_id, knowledge_base_id, user_id, attempt) VALUES (%s,%s,%s,%s,%s)""",
                    (task_id, document_id, knowledge_base_id, user_id, attempt),
                )
                await cursor.execute(
                    "UPDATE knowledge_documents SET status='uploaded', error_code=NULL, error_message=NULL WHERE document_id=%s",
                    (document_id,),
                )
            await connection.commit()
        return await self.get_ingestion_task(user_id, task_id)

    async def recover_interrupted_tasks(self) -> list[str]:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "UPDATE document_ingestion_tasks SET status='pending', stage='uploaded', started_at=NULL WHERE status='processing'"
                )
                await cursor.execute("SELECT task_id FROM document_ingestion_tasks WHERE status='pending' ORDER BY created_at")
                rows = await cursor.fetchall()
            await connection.commit()
        return [row["task_id"] for row in rows]
