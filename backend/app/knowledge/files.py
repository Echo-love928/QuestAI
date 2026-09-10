from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class UploadLike(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


class InvalidDocument(ValueError):
    pass


class FileTooLarge(InvalidDocument):
    pass


@dataclass(frozen=True)
class StoredUpload:
    filename: str
    content_type: str
    extension: str
    size_bytes: int
    sha256: str
    storage_key: str


ALLOWED_MIME = {
    "pdf": {"application/pdf", "application/octet-stream"},
    "doc": {"application/msword", "application/octet-stream"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"},
    "md": {"text/markdown", "text/plain", "application/octet-stream"},
}


def sanitize_filename(filename: str | None) -> str:
    name = Path((filename or "").replace("\\", "/")).name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name or name in {".", ".."} or "." not in name:
        raise InvalidDocument("文件名无效")
    return name[:255]


def validate_document_signature(filename: str, content_type: str | None, content: bytes) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_MIME:
        raise InvalidDocument("仅支持 PDF、DOC、DOCX 和 Markdown 文件")
    normalized_type = (content_type or "application/octet-stream").split(";", 1)[0].lower()
    if normalized_type not in ALLOWED_MIME[extension]:
        raise InvalidDocument("文件类型与扩展名不一致")
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise InvalidDocument("PDF 文件签名无效")
    if extension == "doc" and not content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        raise InvalidDocument("DOC 文件签名无效")
    if extension == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
        except (zipfile.BadZipFile, OSError) as exc:
            raise InvalidDocument("DOCX 文件签名无效") from exc
        if "[Content_Types].xml" not in names or not any(name.startswith("word/") for name in names):
            raise InvalidDocument("DOCX 文件结构无效")
    if extension == "md":
        if b"\x00" in content:
            raise InvalidDocument("Markdown 文件包含二进制内容")
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidDocument("Markdown 文件必须使用 UTF-8 编码") from exc
    return extension


class KnowledgeFileStore:
    def __init__(self, root: Path, *, max_bytes: int) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, upload: UploadLike, *, user_id: int, document_id: str) -> StoredUpload:
        filename = sanitize_filename(upload.filename)
        user_segment = "u_" + hashlib.sha256(str(user_id).encode()).hexdigest()[:20]
        directory = self.root / user_segment / document_id
        directory.mkdir(parents=True, exist_ok=True)
        temp = directory / ".uploading"
        digest = hashlib.sha256()
        total = 0
        header = bytearray()
        try:
            with temp.open("wb") as output:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise FileTooLarge(f"单个文件不能超过 {self.max_bytes // (1024 * 1024)}MB")
                    if len(header) < 2 * 1024 * 1024:
                        header.extend(chunk[: 2 * 1024 * 1024 - len(header)])
                    digest.update(chunk)
                    output.write(chunk)
            if total == 0:
                raise InvalidDocument("文件内容为空")
            extension = validate_document_signature(filename, upload.content_type, bytes(header))
            target = directory / filename
            os.replace(temp, target)
            return StoredUpload(
                filename=filename,
                content_type=(upload.content_type or "application/octet-stream").split(";", 1)[0],
                extension=extension,
                size_bytes=total,
                sha256=digest.hexdigest(),
                storage_key=target.relative_to(self.root).as_posix(),
            )
        except Exception:
            temp.unlink(missing_ok=True)
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
            raise

    def resolve(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if not candidate.is_relative_to(self.root):
            raise InvalidDocument("文件存储路径无效")
        return candidate

    def delete(self, storage_key: str) -> None:
        path = self.resolve(storage_key)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass
