from dataclasses import dataclass
from types import TracebackType
from typing import cast

import pytest
from simcore_postgres_database.db_asyncpg_uow import AsyncpgUnitOfWorkFactory
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass
class _ScopeState:
    closed: bool = False
    committed: bool = False
    rolled_back: bool = False


class _ConnectionScope:
    def __init__(self, connection: AsyncConnection, state: _ScopeState) -> None:
        self._connection = connection
        self._state = state

    async def __aenter__(self) -> AsyncConnection:
        return self._connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self._state.closed = True
        return False


class _TransactionScope(_ConnectionScope):
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self._state.closed = True
        self._state.committed = exc_type is None
        self._state.rolled_back = exc_type is not None
        return False


class _Engine:
    def __init__(self) -> None:
        self.connection = cast(AsyncConnection, object())
        self.read_scopes: list[_ScopeState] = []
        self.transaction_scopes: list[_ScopeState] = []

    def connect(self) -> _ConnectionScope:
        state = _ScopeState()
        self.read_scopes.append(state)
        return _ConnectionScope(self.connection, state)

    def begin(self) -> _TransactionScope:
        state = _ScopeState()
        self.transaction_scopes.append(state)
        return _TransactionScope(self.connection, state)


@pytest.fixture
def asyncpg_uow_factory() -> tuple[AsyncpgUnitOfWorkFactory, _Engine]:
    engine = _Engine()
    return AsyncpgUnitOfWorkFactory(engine=cast(AsyncEngine, engine)), engine
