from typing import Any

import aiomysql

from app.core.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.pool: aiomysql.Pool | None = None

    async def connect(self) -> None:
        self.pool = await aiomysql.create_pool(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
            db=self.settings.mysql_database,
            charset="utf8mb4",
            autocommit=False,
            minsize=1,
            maxsize=10,
        )

    async def close(self) -> None:
        if self.pool is not None:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None

    def require_pool(self) -> aiomysql.Pool:
        if self.pool is None:
            raise RuntimeError("数据库尚未连接")
        return self.pool

    async def fetch_one(self, sql: str, args: tuple[Any, ...] = ()) -> dict | None:
        async with self.require_pool().acquire() as connection:
            await connection.rollback()
            try:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, args)
                    return await cursor.fetchone()
            finally:
                await connection.rollback()

    async def fetch_all(self, sql: str, args: tuple[Any, ...] = ()) -> list[dict]:
        async with self.require_pool().acquire() as connection:
            await connection.rollback()
            try:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, args)
                    return list(await cursor.fetchall())
            finally:
                await connection.rollback()
