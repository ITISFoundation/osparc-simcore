from typing import Protocol, cast

import pytest
from common_library.unit_of_work import ReadUnitOfWork, TransactionalUnitOfWork
from simcore_postgres_database.unit_of_work import (
    SqlAlchemyUnitOfWorkFactory,
    get_sqlalchemy_connection,
    get_sqlalchemy_transaction_connection,
)
from sqlalchemy.ext.asyncio import AsyncConnection


class _ScopeState(Protocol):
    closed: bool
    committed: bool
    rolled_back: bool


class _Engine(Protocol):
    connection: AsyncConnection
    read_scopes: list[_ScopeState]
    transaction_scopes: list[_ScopeState]


type SqlAlchemyUowFixture = tuple[SqlAlchemyUnitOfWorkFactory, _Engine]


class _ForeignReadUnitOfWork(ReadUnitOfWork): ...


class _ForeignTransactionalUnitOfWork(TransactionalUnitOfWork): ...


async def test_read_scope_acquires_lazily_and_closes_owned_connection(
    sqlalchemy_uow_factory: SqlAlchemyUowFixture,
):
    factory, engine = sqlalchemy_uow_factory

    scope = factory.read()
    assert engine.read_scopes == []

    async with scope as unit_of_work:
        assert len(engine.read_scopes) == 1
        assert engine.read_scopes[0].closed is False
        assert get_sqlalchemy_connection(unit_of_work) is engine.connection

    assert engine.read_scopes[0].closed is True


async def test_read_scope_closes_owned_connection_on_error(
    sqlalchemy_uow_factory: SqlAlchemyUowFixture,
):
    factory, engine = sqlalchemy_uow_factory
    expected_error = RuntimeError("read failed")

    with pytest.raises(RuntimeError, match="read failed") as exc_info:
        async with factory.read():
            raise expected_error

    assert exc_info.value is expected_error
    assert engine.read_scopes[0].closed is True


async def test_read_scope_reuses_existing_read_or_transaction_scope(
    sqlalchemy_uow_factory: SqlAlchemyUowFixture,
):
    factory, engine = sqlalchemy_uow_factory

    async with (
        factory.read() as read_unit_of_work,
        factory.read(existing=read_unit_of_work) as reused_unit_of_work,
    ):
        assert reused_unit_of_work is read_unit_of_work
        assert len(engine.read_scopes) == 1

    async with (
        factory.transaction() as transaction_unit_of_work,
        factory.read(existing=transaction_unit_of_work) as reused_unit_of_work,
    ):
        assert reused_unit_of_work is transaction_unit_of_work
        assert len(engine.read_scopes) == 1


async def test_transaction_scope_commits_or_rolls_back_and_closes_owned_connection(
    sqlalchemy_uow_factory: SqlAlchemyUowFixture,
):
    factory, engine = sqlalchemy_uow_factory

    async with factory.transaction() as unit_of_work:
        assert get_sqlalchemy_transaction_connection(unit_of_work) is engine.connection

    committed_state = engine.transaction_scopes[0]
    assert committed_state.closed is True
    assert committed_state.committed is True
    assert committed_state.rolled_back is False

    expected_error = RuntimeError("rollback")
    with pytest.raises(RuntimeError, match="rollback") as exc_info:
        async with factory.transaction():
            raise expected_error

    assert exc_info.value is expected_error
    rolled_back_state = engine.transaction_scopes[1]
    assert rolled_back_state.closed is True
    assert rolled_back_state.committed is False
    assert rolled_back_state.rolled_back is True


async def test_transaction_scope_reuses_existing_scope_without_owning_it(
    sqlalchemy_uow_factory: SqlAlchemyUowFixture,
):
    factory, engine = sqlalchemy_uow_factory

    async with factory.transaction() as unit_of_work:
        outer_state = engine.transaction_scopes[0]

        async with factory.transaction(existing=unit_of_work) as reused_unit_of_work:
            assert reused_unit_of_work is unit_of_work
            assert len(engine.transaction_scopes) == 1

        assert outer_state.closed is False
        assert outer_state.committed is False
        assert outer_state.rolled_back is False

    assert outer_state.closed is True
    assert outer_state.committed is True
    assert outer_state.rolled_back is False


async def test_transaction_scope_rejects_read_only_and_foreign_units_of_work(
    sqlalchemy_uow_factory: SqlAlchemyUowFixture,
):
    factory, _ = sqlalchemy_uow_factory

    async with factory.read() as read_unit_of_work:
        with pytest.raises(TypeError, match="transactional unit of work"):
            async with factory.transaction(existing=cast(TransactionalUnitOfWork, read_unit_of_work)):
                pytest.fail("read-only unit of work was accepted for a transaction")

    with pytest.raises(TypeError, match="SQLAlchemy unit of work"):
        async with factory.read(existing=_ForeignReadUnitOfWork()):
            pytest.fail("foreign read unit of work was accepted")

    with pytest.raises(TypeError, match="transactional unit of work"):
        async with factory.transaction(existing=_ForeignTransactionalUnitOfWork()):
            pytest.fail("foreign transactional unit of work was accepted")
