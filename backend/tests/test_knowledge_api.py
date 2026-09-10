from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.knowledge import (
    DocumentIngestionTask,
    DocumentUploadAccepted,
    KnowledgeBaseDetail,
    KnowledgeBaseSummary,
    KnowledgeDocument,
)
from tests.test_api import ApiGateway
from tests.test_auth_api import FakeUserService


NOW = datetime.now(timezone.utc)


def summary() -> KnowledgeBaseSummary:
    return KnowledgeBaseSummary(id=3, name="客服资料", document_count=1, ready_document_count=1, chunk_count=8, created_at=NOW, updated_at=NOW)


def document() -> KnowledgeDocument:
    return KnowledgeDocument(document_id="doc_safe", knowledge_base_id=3, filename="内部规范.pdf", content_type="application/pdf", size_bytes=128, status="ready", chunk_count=8, created_at=NOW, updated_at=NOW)


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.deleted = []

    async def create(self, user_id, payload): return summary()
    async def list(self, user_id): return [summary()]
    async def validate_selection(self, user_id, knowledge_base_ids): return None
    async def detail(self, user_id, kb_id): return KnowledgeBaseDetail(**summary().model_dump(), documents=[document()])
    async def update(self, user_id, kb_id, payload): return summary().model_copy(update=payload.model_dump(exclude_unset=True))
    async def delete(self, user_id, kb_id): self.deleted.append((user_id, kb_id))
    async def upload(self, user_id, kb_id, upload):
        return DocumentUploadAccepted(
            document=document().model_copy(update={"status": "uploaded"}),
            task=DocumentIngestionTask(task_id="ingest_safe", document_id="doc_safe", status="pending", stage="uploaded"),
        )
    async def list_documents(self, user_id, kb_id): return [document()]
    async def document(self, user_id, kb_id, doc_id): return document()
    async def delete_document(self, user_id, kb_id, doc_id): self.deleted.append((user_id, kb_id, doc_id))
    async def reindex(self, user_id, kb_id, doc_id): return DocumentIngestionTask(task_id="retry", document_id=doc_id, status="pending", stage="uploaded")


def app_and_headers():
    users = FakeUserService()
    service = FakeKnowledgeService()
    app = create_app(gateway=ApiGateway(), user_service=users, learning_repository=object(), knowledge_service=service)
    token = users.tokens.create_access_token(users.user.id)
    return app, service, {"Authorization": f"Bearer {token}"}


async def request(app, method, path, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.anyio
async def test_all_knowledge_endpoints_require_login() -> None:
    app, _, _ = app_and_headers()
    response = await request(app, "GET", "/api/v1/knowledge-bases")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_knowledge_base_crud_and_safe_detail() -> None:
    app, service, headers = app_and_headers()
    created = await request(app, "POST", "/api/v1/knowledge-bases", headers=headers, json={"name": "客服资料"})
    listing = await request(app, "GET", "/api/v1/knowledge-bases", headers=headers)
    detail_response = await request(app, "GET", "/api/v1/knowledge-bases/3", headers=headers)
    updated = await request(app, "PUT", "/api/v1/knowledge-bases/3", headers=headers, json={"description": "培训"})
    deleted = await request(app, "DELETE", "/api/v1/knowledge-bases/3", headers=headers)
    assert created.status_code == listing.status_code == detail_response.status_code == updated.status_code == 200
    assert deleted.status_code == 204
    payload = detail_response.text
    assert "storage_key" not in payload and "collection" not in payload and "openid" not in payload
    assert service.deleted == [(7, 3)]


@pytest.mark.anyio
async def test_upload_returns_202_and_document_routes_work() -> None:
    app, service, headers = app_and_headers()
    uploaded = await request(
        app, "POST", "/api/v1/knowledge-bases/3/documents", headers=headers,
        files={"file": ("内部规范.pdf", b"%PDF-content", "application/pdf")},
    )
    listing = await request(app, "GET", "/api/v1/knowledge-bases/3/documents", headers=headers)
    detail_response = await request(app, "GET", "/api/v1/knowledge-bases/3/documents/doc_safe", headers=headers)
    retry = await request(app, "POST", "/api/v1/knowledge-bases/3/documents/doc_safe/reindex", headers=headers)
    deleted = await request(app, "DELETE", "/api/v1/knowledge-bases/3/documents/doc_safe", headers=headers)
    assert uploaded.status_code == 202
    assert uploaded.json()["data"]["task"]["status"] == "pending"
    assert listing.status_code == detail_response.status_code == retry.status_code == 200
    assert deleted.status_code == 204
    assert service.deleted[-1] == (7, 3, "doc_safe")
