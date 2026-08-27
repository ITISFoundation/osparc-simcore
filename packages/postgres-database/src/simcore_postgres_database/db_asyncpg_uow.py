from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

from common_library.unit_of_work import (
    ReadUnitOfWork,
    TransactionalUnitOfWork,
    UnitOfWorkFactory,
)
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass(frozen=True, kw_only=True, slots=True)
class _AsyncpgReadUnitOfWork(ReadUnitOfWork):
    connection: AsyncConnection


@dataclass(frozen=True, kw_only=True, slots=True)
class _AsyncpgTransactionalUnitOfWork(TransactionalUnitOfWork):
    connection: AsyncConnection


def get_asyncpg_connection(unit_of_work: ReadUnitOfWork) -> AsyncConnection:
    if isinstance(unit_of_work, (_AsyncpgReadUnitOfWork, _AsyncpgTransactionalUnitOfWork)):
        return unit_of_work.connection
    msg = f"Expected an Asyncpg unit of work, got {type(unit_of_work).__name__}"
    raise TypeError(msg)


def get_asyncpg_transaction_connection(
    unit_of_work: TransactionalUnitOfWork,
) -> AsyncConnection:
    if isinstance(unit_of_work, _AsyncpgTransactionalUnitOfWork):
        return unit_of_work.connection
    msg = f"Expected an Asyncpg transactional unit of work, got {type(unit_of_work).__name__}"
    raise TypeError(msg)


@asynccontextmanager
async def _read_scope(
    engine: AsyncEngine,
    existing: ReadUnitOfWork | None,
) -> AsyncIterator[ReadUnitOfWork]:
    if existing is not None:
        get_asyncpg_connection(existing)
        yield existing
        return

    async with engine.connect() as connection:
        yield _AsyncpgReadUnitOfWork(connection=connection)


@asynccontextmanager
async def _transaction_scope(
    engine: AsyncEngine,
    existing: TransactionalUnitOfWork | None,
) -> AsyncIterator[TransactionalUnitOfWork]:
    if existing is not None:
        get_asyncpg_transaction_connection(existing)
        yield existing
        return

    async with engine.begin() as connection:
        yield _AsyncpgTransactionalUnitOfWork(connection=connection)


@dataclass(frozen=True, kw_only=True, slots=True)
class AsyncpgUnitOfWorkFactory(UnitOfWorkFactory):
    engine: AsyncEngine

    def read(
        self,
        *,
        existing: ReadUnitOfWork | None = None,
    ) -> AbstractAsyncContextManager[ReadUnitOfWork]:
        return _read_scope(self.engine, existing)

    def transaction(
        self,
        *,
        existing: TransactionalUnitOfWork | None = None,
    ) -> AbstractAsyncContextManager[TransactionalUnitOfWork]:
        return _transaction_scope(self.engine, existing)
