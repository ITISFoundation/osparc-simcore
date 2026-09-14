from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class BaseRepository:
    engine: AsyncEngine
