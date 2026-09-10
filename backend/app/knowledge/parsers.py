from __future__ import annotations

import asyncio
import re
from pathlib import Path

import docx2txt
from langchain_core.documents import Document
from pypdf import PdfReader


class DocumentParseError(ValueError):
    pass


def clean_text(value: str) -> str:
    value = value.replace("\x00", "")
    value = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return value.strip()


class LegacyDocParser:
    def __init__(self, server_endpoint: str = "") -> None:
        self.server_endpoint = server_endpoint

    async def extract(self, path: Path) -> str:
        def run() -> str:
            try:
                from tika import parser

                kwargs = {"serverEndpoint": self.server_endpoint} if self.server_endpoint else {}
                parsed = parser.from_file(str(path), **kwargs)
                return str((parsed or {}).get("content") or "")
            except Exception as exc:
                raise DocumentParseError("旧版 DOC 解析服务不可用，请转换为 DOCX 后重试") from exc

        return await asyncio.to_thread(run)


class DocumentParser:
    def __init__(self, *, max_chars: int, legacy_parser: LegacyDocParser | None = None) -> None:
        self.max_chars = max_chars
        self.legacy_parser = legacy_parser or LegacyDocParser()

    async def parse(self, path: Path, extension: str) -> list[Document]:
        extension = extension.lower().lstrip(".")
        if extension == "pdf":
            documents = await asyncio.to_thread(self._parse_pdf, path)
        elif extension == "docx":
            text = await asyncio.to_thread(docx2txt.process, str(path))
            documents = [Document(page_content=clean_text(text or ""), metadata={"source_type": "docx"})]
        elif extension == "md":
            text = await asyncio.to_thread(path.read_text, encoding="utf-8-sig")
            documents = [Document(page_content=clean_text(text), metadata={"source_type": "markdown"})]
        elif extension == "doc":
            text = await self.legacy_parser.extract(path)
            documents = [Document(page_content=clean_text(text), metadata={"source_type": "legacy_doc"})]
        else:
            raise DocumentParseError("不支持的文档格式")
        documents = [doc for doc in documents if len(doc.page_content.strip()) >= 8]
        if not documents:
            raise DocumentParseError("文档没有可用文本；扫描 PDF 暂不支持 OCR")
        total = sum(len(doc.page_content) for doc in documents)
        if total > self.max_chars:
            raise DocumentParseError("文档文本过长，请拆分后上传")
        return documents

    @staticmethod
    def _parse_pdf(path: Path) -> list[Document]:
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                raise DocumentParseError("不支持加密 PDF")
            return [
                Document(page_content=clean_text(page.extract_text() or ""), metadata={"source_type": "pdf", "page": index})
                for index, page in enumerate(reader.pages, start=1)
            ]
        except DocumentParseError:
            raise
        except Exception as exc:
            raise DocumentParseError("PDF 解析失败") from exc
