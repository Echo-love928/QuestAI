from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_async_quiz_task_migration_has_required_contract() -> None:
    sql = (
        BACKEND_DIR / "sql" / "migrations" / "003_add_quiz_generation_tasks.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS `quiz_generation_tasks`" in sql
    for column in (
        "task_id",
        "user_id",
        "status",
        "request_json",
        "result_json",
        "error_code",
        "error_message",
    ):
        assert f"`{column}`" in sql
    for status in ("pending", "processing", "completed", "failed"):
        assert f"'{status}'" in sql
