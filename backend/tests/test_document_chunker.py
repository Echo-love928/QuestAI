import pytest
from langchain_core.documents import Document

from app.knowledge.chunking import DocumentChunker


def test_chunker_produces_stable_ids_and_preserves_page_metadata() -> None:
    chunker = DocumentChunker(chunk_size=30, chunk_overlap=5, max_chunks=20)
    docs = [Document(page_content="第一段内容。" * 8, metadata={"page": 3, "section": "流程"})]
    chunks = chunker.split(docs, knowledge_base_id=2, document_id="doc_a", filename="规范.pdf", index_version=4)
    assert len(chunks) > 1
    assert chunks[0].chunk_id == "kb:2:doc:doc_a:chunk:0:v4"
    assert chunks[0].page == 3
    assert chunks[0].section == "流程"


def test_chunk_count_is_bounded() -> None:
    chunker = DocumentChunker(chunk_size=10, chunk_overlap=0, max_chunks=2)
    with pytest.raises(ValueError, match="片段"):
        chunker.split([Document(page_content="内容。" * 100)], knowledge_base_id=1, document_id="d", filename="a.md")
