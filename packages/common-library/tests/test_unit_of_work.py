import inspect
from contextlib import AbstractAsyncContextManager
from types import TracebackType

from common_library.unit_of_work import (
    ReadUnitOfWork,
    TransactionalUnitOfWork,
    UnitOfWorkFactory,
)


class _ReadUnitOfWork(ReadUnitOfWork): ...


class _TransactionalUnitOfWork(TransactionalUnitOfWork): ...


class _UnitOfWorkContext[UnitOfWorkT: ReadUnitOfWork]:
    def __init__(self, unit_of_work: UnitOfWorkT) -> None:
        self._unit_of_work = unit_of_work

    async def __aenter__(self) -> UnitOfWorkT:
        return self._unit_of_work

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False


class _IncompleteUnitOfWorkFactory(UnitOfWorkFactory): ...


class _UnitOfWorkFactory(UnitOfWorkFactory):
    def read(
        self,
        *,
        existing: ReadUnitOfWork | None = None,
    ) -> AbstractAsyncContextManager[ReadUnitOfWork]:
        self._read_calls += 1
        return _UnitOfWorkContext(existing or _ReadUnitOfWork())

    def transaction(
        self,
        *,
        existing: TransactionalUnitOfWork | None = None,
    ) -> AbstractAsyncContextManager[TransactionalUnitOfWork]:
        self._transaction_calls += 1
        return _UnitOfWorkContext(existing or _TransactionalUnitOfWork())

    def __init__(self) -> None:
        self._read_calls = 0
        self._transaction_calls = 0


def test_incomplete_unit_of_work_factory_cannot_be_instantiated():
    assert inspect.isabstract(_IncompleteUnitOfWorkFactory)


async def test_unit_of_work_factory_contract_supports_new_and_existing_scopes():
    factory = _UnitOfWorkFactory()

    async with factory.read() as read_uow:
        assert isinstance(read_uow, ReadUnitOfWork)
        async with factory.read(existing=read_uow) as reused_read_uow:
            assert reused_read_uow is read_uow

    async with factory.transaction() as transactional_uow:
        assert isinstance(transactional_uow, TransactionalUnitOfWork)
        assert isinstance(transactional_uow, ReadUnitOfWork)
        async with factory.transaction(existing=transactional_uow) as reused_transactional_uow:
            assert reused_transactional_uow is transactional_uow
