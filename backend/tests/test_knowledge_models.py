from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseSummary,
    KnowledgeBaseUpdate,
    KnowledgeDocument,
)


def test_knowledge_base_name_and_description_are_normalized() -> None:
    request = KnowledgeBaseCreate(name="  客服  新人训练营 ", description="  培训资料  ")
    assert request.name == "客服 新人训练营"
    assert request.description == "培训资料"


@pytest.mark.parametrize("name", ["", "   ", "a" * 31])
def test_invalid_knowledge_base_name_is_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        KnowledgeBaseCreate(name=name)


def test_empty_update_is_rejected() -> None:
    with pytest.raises(ValidationError):
        KnowledgeBaseUpdate()


def test_document_response_never_contains_storage_key() -> None:
    document = KnowledgeDocument(
        document_id="doc_123",
        knowledge_base_id=1,
        filename="内部规范.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        status="ready",
        chunk_count=12,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    payload = document.model_dump()
    assert "storage_key" not in payload
    assert "collection_name" not in payload


def test_summary_reports_document_counts() -> None:
    summary = KnowledgeBaseSummary(
        id=1,
        name="客服资料",
        document_count=3,
        ready_document_count=2,
        chunk_count=30,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert summary.document_count == 3
    assert summary.ready_document_count == 2
