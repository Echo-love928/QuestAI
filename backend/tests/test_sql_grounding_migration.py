from pathlib import Path


SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def test_grounding_migration_is_guarded_and_drops_temporary_procedure() -> None:
    sql = (SQL_DIR / "migrations" / "002_add_quiz_grounding.sql").read_text(
        encoding="utf-8"
    )

    assert sql.count("IF NOT EXISTS") >= 3
    assert "information_schema.COLUMNS" in sql
    assert "DROP PROCEDURE IF EXISTS `add_quiz_grounding_columns`" in sql
    assert "grounding_mode" in sql
    assert "sources_json" in sql
    assert "researched_at" in sql


def test_initial_schema_contains_final_grounding_columns() -> None:
    sql = (SQL_DIR / "init_mysql.sql").read_text(encoding="utf-8")

    assert "`grounding_mode` VARCHAR(32) NULL" in sql
    assert "`sources_json` JSON NULL" in sql
    assert "`researched_at` DATETIME(3) NULL" in sql
