from pathlib import Path

from app.knowledge.chunking import KnowledgeChunk
from app.knowledge.vector_store import ChromaKnowledgeStore, collection_name_for_user
import pytest


def test_collection_name_is_stable_and_does_not_expose_user_id() -> None:
    first = collection_name_for_user(123)
    assert first == collection_name_for_user(123)
    assert first != collection_name_for_user(124)
    assert "123" not in first


def test_chroma_upsert_query_filter_and_delete(tmp_path: Path) -> None:
    store = ChromaKnowledgeStore(tmp_path)
    chunks = [
        KnowledgeChunk("c1", "退款处理流程", 10, "doc_a", "制度.pdf", 0, page=2),
        KnowledgeChunk("c2", "公开产品介绍", 11, "doc_b", "产品.md", 0),
    ]
    store.upsert(7, chunks, [[1.0, 0.0], [0.0, 1.0]])

    matches = store.query(7, [1.0, 0.0], knowledge_base_ids=[10], limit=5)
    assert [item.document_id for item in matches] == ["doc_a"]
    assert matches[0].page == 2
    assert matches[0].score > 0.99
    assert store.query(8, [1.0, 0.0], knowledge_base_ids=[10], limit=5) == []

    store.delete_document(7, "doc_a")
    assert store.query(7, [1.0, 0.0], knowledge_base_ids=[10], limit=5) == []


def test_chroma_does_not_hide_storage_failures(tmp_path: Path) -> None:
    class BrokenClient:
        def get_collection(self, _name):
            raise RuntimeError("disk unavailable")

    store = ChromaKnowledgeStore(tmp_path, client=BrokenClient())
    with pytest.raises(RuntimeError, match="disk unavailable"):
        store.delete_document(7, "doc_a")
