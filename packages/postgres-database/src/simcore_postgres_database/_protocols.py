"""Common protocols to annotate equivalent connections:
    - sqlalchemy.ext.asyncio.AsyncConnection
    - aiopg.sa.connection.SAConnection

Purpose: to reduce dependency with aiopg (expected full migration to asyncpg)
"""

from collections.abc import Coroutine
from typing import Any, Protocol, TypeVar

from sqlalchemy.sql.dml import Delete, Insert, Update
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.selectable import Select

# Type for query results
Result = TypeVar("Result")

# Type alias for methods that can be either async or sync
MaybeCoro = Coroutine[Any, Any, Result] | Result


class ResultProxy(Protocol):
    """Protocol for query result objects from both engines

    Handles both aiopg's async methods and SQLAlchemy asyncpg's sync methods.
    The caller should handle both cases, for example:

    result = await conn.execute(query)
    row = await result.fetchone() if hasattr(result.fetchone, '__await__') else result.fetchone()
    """

    def fetchall(self) -> MaybeCoro[list[Any]]: ...
    def fetchone(self) -> MaybeCoro[Any | None]: ...
    def first(self) -> MaybeCoro[Any | None]: ...
    def scalar(self) -> MaybeCoro[Any | None]: ...
    def scalar_one_or_none(self) -> Any | None: ...


class DBConnection(Protocol):
    """Protocol to account for both aiopg and SQLAlchemy async connections"""

    async def scalar(
        self, statement: Select | Insert | Update | Delete | TextClause, **kwargs
    ) -> Any:
        """Execute a statement and return a scalar result"""
        ...

    async def execute(
        self, statement: Select | Insert | Update | Delete | TextClause, **kwargs
    ) -> ResultProxy:
        """Execute a statement and return a result proxy"""
        ...

    async def begin(self) -> Any:
        """Begin a transaction"""
        ...

    async def begin_nested(self) -> Any:
        """Begin a nested transaction (savepoint)"""
        ...
