"""Apply one trusted SQL migration using the database configured in .env."""

import argparse
import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.db.database import Database


def statements_from(path: Path) -> list[str]:
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    ]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


async def apply(path: Path) -> None:
    database = Database(get_settings())
    await database.connect()
    try:
        async with database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                for statement in statements_from(path):
                    await cursor.execute(statement)
            await connection.commit()
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    asyncio.run(apply(args.path))
