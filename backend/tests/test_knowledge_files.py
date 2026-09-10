import io
import zipfile
from pathlib import Path

import pytest

from app.knowledge.files import (
    FileTooLarge,
    InvalidDocument,
    KnowledgeFileStore,
    sanitize_filename,
    validate_document_signature,
)


class FakeUpload:
    def __init__(self, content: bytes, filename: str = "资料.md", content_type: str = "text/markdown") -> None:
        self._stream = io.BytesIO(content)
        self.filename = filename
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def make_docx_header() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return buffer.getvalue()


def test_filename_is_reduced_to_safe_display_name() -> None:
    assert sanitize_filename("../../内部:制度?.PDF") == "内部_制度_.PDF"
    with pytest.raises(InvalidDocument):
        sanitize_filename("....")


@pytest.mark.parametrize(
    ("filename", "content_type", "content"),
    [
        ("a.pdf", "application/pdf", b"%PDF-1.7\n"),
        ("a.doc", "application/msword", bytes.fromhex("D0CF11E0A1B11AE1") + b"x"),
        ("a.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", make_docx_header()),
        ("a.md", "text/markdown", "# 标题\n正文".encode()),
    ],
)
def test_supported_document_signatures(filename: str, content_type: str, content: bytes) -> None:
    assert validate_document_signature(filename, content_type, content)


def test_spoofed_extension_is_rejected() -> None:
    with pytest.raises(InvalidDocument):
        validate_document_signature("secret.pdf", "application/pdf", b"not a pdf")


@pytest.mark.anyio
async def test_upload_is_streamed_hashed_and_resolved_under_root(tmp_path: Path) -> None:
    store = KnowledgeFileStore(tmp_path, max_bytes=1024)
    stored = await store.save(FakeUpload("# 私有资料\n正文".encode()), user_id=7, document_id="doc_x")

    assert stored.size_bytes > 0
    assert len(stored.sha256) == 64
    assert stored.storage_key.startswith("u_")
    resolved = store.resolve(stored.storage_key)
    assert resolved.is_file()
    assert resolved.is_relative_to(tmp_path.resolve())


@pytest.mark.anyio
async def test_oversized_upload_leaves_no_file(tmp_path: Path) -> None:
    store = KnowledgeFileStore(tmp_path, max_bytes=5)
    with pytest.raises(FileTooLarge):
        await store.save(FakeUpload(b"123456"), user_id=1, document_id="doc_large")
    assert list(tmp_path.rglob("*.*")) == []


def test_storage_key_cannot_escape_root(tmp_path: Path) -> None:
    store = KnowledgeFileStore(tmp_path, max_bytes=10)
    with pytest.raises(InvalidDocument):
        store.resolve("../../outside.md")
