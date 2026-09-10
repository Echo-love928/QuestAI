from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_knowledge_migration_has_required_tables_columns_and_constraints() -> None:
    sql = (BACKEND_DIR / "sql" / "migrations" / "004_add_private_knowledge_base.sql").read_text(encoding="utf-8")

    for table in ("knowledge_bases", "knowledge_documents", "document_ingestion_tasks"):
        assert f"CREATE TABLE IF NOT EXISTS `{table}`" in sql
    for column in (
        "user_id", "knowledge_base_id", "document_id", "storage_key",
        "sha256", "status", "chunk_count", "embedding_model", "embedding_dimensions",
    ):
        assert f"`{column}`" in sql
    for status in ("uploaded", "parsing", "chunking", "embedding", "ready", "failed"):
        assert f"'{status}'" in sql
    assert "ON DELETE CASCADE" in sql
    assert "IF NOT EXISTS" in sql


def test_init_sql_contains_knowledge_schema_for_new_installations() -> None:
    sql = (BACKEND_DIR / "sql" / "init_mysql.sql").read_text(encoding="utf-8")

    for table in ("knowledge_bases", "knowledge_documents", "document_ingestion_tasks"):
        assert f"CREATE TABLE IF NOT EXISTS `{table}`" in sql
