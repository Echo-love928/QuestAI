from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    content: str
    knowledge_base_id: int
    document_id: str
    filename: str
    chunk_index: int
    page: int | None = None
    section: str | None = None


class DocumentChunker:
    def __init__(self, *, chunk_size: int, chunk_overlap: int, max_chunks: int) -> None:
        self.max_chunks = max_chunks
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ";", "；", "，", " ", ""],
        )

    def split(
        self, documents: list[Document], *, knowledge_base_id: int, document_id: str,
        filename: str, index_version: int = 1,
    ) -> list[KnowledgeChunk]:
        split_docs = self.splitter.split_documents(documents)
        if len(split_docs) > self.max_chunks:
            raise ValueError("文档产生的知识片段过多，请拆分后上传")
        return [
            KnowledgeChunk(
                chunk_id=f"kb:{knowledge_base_id}:doc:{document_id}:chunk:{index}:v{index_version}",
                content=doc.page_content,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                filename=filename,
                chunk_index=index,
                page=doc.metadata.get("page"),
                section=doc.metadata.get("section"),
            )
            for index, doc in enumerate(split_docs)
        ]
