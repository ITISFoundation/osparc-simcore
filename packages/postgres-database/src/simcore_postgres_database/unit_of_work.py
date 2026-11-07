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
class _SqlAlchemyReadUnitOfWork(ReadUnitOfWork):
    connection: AsyncConnection


@dataclass(frozen=True, kw_only=True, slots=True)
class _SqlAlchemyTransactionalUnitOfWork(TransactionalUnitOfWork):
    connection: AsyncConnection


def get_sqlalchemy_connection(unit_of_work: ReadUnitOfWork) -> AsyncConnection:
    if isinstance(
        unit_of_work,
        (_SqlAlchemyReadUnitOfWork, _SqlAlchemyTransactionalUnitOfWork),
    ):
        return unit_of_work.connection
    msg = f"Expected a SQLAlchemy unit of work, got {type(unit_of_work).__name__}"
    raise TypeError(msg)


def get_sqlalchemy_transaction_connection(
    unit_of_work: TransactionalUnitOfWork,
) -> AsyncConnection:
    if isinstance(unit_of_work, _SqlAlchemyTransactionalUnitOfWork):
        return unit_of_work.connection
    msg = f"Expected a SQLAlchemy transactional unit of work, got {type(unit_of_work).__name__}"
    raise TypeError(msg)


@asynccontextmanager
async def _read_scope(
    engine: AsyncEngine,
    existing: ReadUnitOfWork | None,
) -> AsyncIterator[ReadUnitOfWork]:
    if existing is not None:
        get_sqlalchemy_connection(existing)
        yield existing
        return

    async with engine.connect() as connection:
        yield _SqlAlchemyReadUnitOfWork(connection=connection)


@asynccontextmanager
async def _transaction_scope(
    engine: AsyncEngine,
    existing: TransactionalUnitOfWork | None,
) -> AsyncIterator[TransactionalUnitOfWork]:
    if existing is not None:
        get_sqlalchemy_transaction_connection(existing)
        yield existing
        return

    async with engine.begin() as connection:
        yield _SqlAlchemyTransactionalUnitOfWork(connection=connection)


@dataclass(frozen=True, kw_only=True, slots=True)
class SqlAlchemyUnitOfWorkFactory(UnitOfWorkFactory):
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
