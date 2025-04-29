"""Common protocols to annotate equivalent connections:
    - sqlalchemy.ext.asyncio.AsyncConnection
    - aiopg.sa.connection.SAConnection

Purpose: to reduce dependency with aiopg (expected full migration to asyncpg)
"""

from collections.abc import Awaitable
from typing import Any, Protocol, TypeAlias, TypeVar

from sqlalchemy.sql import Executable

# Type for query results
Result = TypeVar("Result")

# Type alias for methods that can be either async or sync
MaybeCoro: TypeAlias = Awaitable[Result] | Result


class ResultProxy(Protocol):
    """Protocol for query result objects from both engines

    Handles both aiopg's async methods and SQLAlchemy asyncpg's sync methods.
    This is temporary until we fully migrate to asyncpg.
    """

    def fetchall(self) -> MaybeCoro[list[Any]]: ...
    def fetchone(self) -> MaybeCoro[Any | None]: ...
    def first(self) -> MaybeCoro[Any | None]: ...


class DBConnection(Protocol):
    """Protocol to account for both aiopg and SQLAlchemy async connections"""

    async def scalar(
        self,
        statement: Executable,
        parameters: dict[str, Any] | None = None,
        *,
        execution_options: dict[str, Any] | None = None,
    ) -> Any: ...

    async def execute(
        self,
        statement: Executable,
        parameters: dict[str, Any] | None = None,
        *,
        execution_options: dict[str, Any] | None = None,
    ) -> ResultProxy: ...
