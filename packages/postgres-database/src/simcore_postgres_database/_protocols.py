"""Common protocols to annotate equivalent connections:
        - sqlalchemy.ext.asyncio.AsyncConnection
        - aiopg.sa.connection.SAConnection


    Purpose: to reduce dependency wit aiopg (expected full migration to asyncpg)
"""

from typing import Protocol


class DBConnection(Protocol):
    # Prototype to account for aiopg and asyncio connection classes, i.e.
    #   from aiopg.sa.connection import SAConnection
    #   from sqlalchemy.ext.asyncio import AsyncConnection
    async def scalar(self, *args, **kwargs):
        ...

    async def execute(self, *args, **kwargs):
        ...

    async def begin(self):
        ...


class AiopgConnection(Protocol):
    # Prototype to account for aiopg-only (this protocol avoids import <-> installation)
    async def scalar(self, *args, **kwargs):
        ...

    async def execute(self, *args, **kwargs):
        ...

    async def begin(self):
        ...
