from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager


class ReadUnitOfWork:
    """Opaque persistence scope for sequential reads."""


class TransactionalUnitOfWork(ReadUnitOfWork):
    """Opaque persistence scope for sequential reads and writes."""


class UnitOfWorkFactory(ABC):
    @abstractmethod
    def read(
        self,
        *,
        existing: ReadUnitOfWork | None = None,
    ) -> AbstractAsyncContextManager[ReadUnitOfWork]: ...

    @abstractmethod
    def transaction(
        self,
        *,
        existing: TransactionalUnitOfWork | None = None,
    ) -> AbstractAsyncContextManager[TransactionalUnitOfWork]: ...
