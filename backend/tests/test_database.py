import pytest

from app.core.config import Settings
from app.db.database import Database


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def execute(self, sql, args):
        self.sql = sql
        self.args = args

    async def fetchone(self):
        return self.rows[0] if self.rows else None

    async def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.rollback_count = 0

    def cursor(self, *_):
        return FakeCursor(self.rows)

    async def rollback(self):
        self.rollback_count += 1


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return None


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return FakeAcquire(self.connection)


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["fetch_one", "fetch_all"])
async def test_reads_reset_reused_connection_transaction_before_and_after(method: str) -> None:
    database = Database(Settings(_env_file=None))
    connection = FakeConnection([{"id": 1}])
    database.pool = FakePool(connection)

    result = await getattr(database, method)("SELECT id FROM example WHERE id = %s", (1,))

    assert result == ({"id": 1} if method == "fetch_one" else [{"id": 1}])
    assert connection.rollback_count == 2
