from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class BaseRepository:
    engine: AsyncEngine
