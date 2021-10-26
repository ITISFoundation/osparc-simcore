from aiopg.sa.engine import Engine

from .utils_migration import get_current_head

ENGINE_ATTRS = "closed driver dsn freesize maxsize minsize name size timeout".split()


class DBMigrationError(RuntimeError):
    pass


async def raise_if_migration_not_ready(engine: Engine):
    """Ensures db migration is complete

    :raises DBMigrationError
    :raises
    """
    async with engine.acquire() as conn:
        version_num = await conn.scalar('SELECT "version_num" FROM "alembic_version"')
        head_version_num = get_current_head()
        if version_num != head_version_num:
            raise DBMigrationError(
                f"Migration is incomplete, expected {head_version_num} but got {version_num}"
            )


async def close_engine(engine: Engine) -> None:
    engine.close()
    await engine.wait_closed()
