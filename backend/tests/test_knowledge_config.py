from pathlib import Path

from app.core.config import BACKEND_DIR, Settings


def test_knowledge_defaults_use_safe_local_paths() -> None:
    settings = Settings(_env_file=None)

    assert settings.embedding_model == "text-embedding-v4"
    assert settings.embedding_dimensions == 1024
    assert settings.embedding_batch_size == 10
    assert settings.knowledge_file_max_bytes == 10 * 1024 * 1024
    assert settings.knowledge_upload_dir == BACKEND_DIR / "uploads" / "knowledge"
    assert settings.chroma_persist_dir == BACKEND_DIR / "data" / "chroma"


def test_relative_knowledge_paths_are_resolved_under_backend() -> None:
    settings = Settings(
        _env_file=None,
        knowledge_upload_dir=Path("private/files"),
        chroma_persist_dir=Path("private/chroma"),
    )

    assert settings.knowledge_upload_dir == BACKEND_DIR / "private" / "files"
    assert settings.chroma_persist_dir == BACKEND_DIR / "private" / "chroma"


def test_secret_is_not_exposed_in_settings_repr() -> None:
    secret = "a-private-bailian-secret"
    settings = Settings(_env_file=None, dashscope_api_key=secret)

    assert secret not in repr(settings)


def test_chunk_overlap_must_be_smaller_than_chunk_size() -> None:
    try:
        Settings(
            _env_file=None,
            knowledge_chunk_size=200,
            knowledge_chunk_overlap=200,
        )
    except ValueError as exc:
        assert "分块重叠" in str(exc)
    else:
        raise AssertionError("invalid chunk settings should fail")
