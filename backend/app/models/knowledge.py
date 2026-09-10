from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


DocumentStatus = Literal[
    "uploaded", "parsing", "chunking", "embedding", "ready", "failed", "deleting"
]
IngestionTaskStatus = Literal["pending", "processing", "completed", "failed"]
IngestionStage = Literal["uploaded", "parsing", "chunking", "embedding", "ready", "failed"]


def _clean_text(value: str) -> str:
    return " ".join(value.split())


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=300)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("知识库名称不能为空")
        return cleaned

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_text(value)
        return cleaned or None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=300)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("知识库名称不能为空")
        return cleaned

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_text(value) or None

    @model_validator(mode="after")
    def require_change(self) -> "KnowledgeBaseUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个修改字段")
        return self


class KnowledgeBaseSummary(BaseModel):
    id: int
    name: str
    description: str | None = None
    document_count: int = 0
    ready_document_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseDetail(KnowledgeBaseSummary):
    documents: list["KnowledgeDocument"] = Field(default_factory=list)


class KnowledgeDocument(BaseModel):
    document_id: str
    knowledge_base_id: int
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    error_code: str | None = None
    error_message: str | None = None
    chunk_count: int = 0
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    index_version: int = 1
    created_at: datetime
    updated_at: datetime


class DocumentIngestionTask(BaseModel):
    task_id: str
    document_id: str
    status: IngestionTaskStatus
    stage: IngestionStage
    attempt: int = 1
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentUploadAccepted(BaseModel):
    document: KnowledgeDocument
    task: DocumentIngestionTask


class StoredDocument(BaseModel):
    document_id: str
    knowledge_base_id: int
    user_id: int
    filename: str
    content_type: str
    extension: str
    size_bytes: int
    sha256: str
    storage_key: str
    status: DocumentStatus
    index_version: int = 1


class RetrievedChunk(BaseModel):
    chunk_id: str
    knowledge_base_id: int
    document_id: str
    filename: str
    content: str
    score: float = Field(ge=0, le=1)
    chunk_index: int
    page: int | None = None
    section: str | None = None
