from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncEngine

RepositoryType = TypeVar("RepositoryType", bound="BaseRepository")


@dataclass
class BaseRepository:
    db_engine: AsyncEngine

    @classmethod
    def instance(cls: type[RepositoryType], db_engine: AsyncEngine) -> RepositoryType:
        return cls(db_engine=db_engine)
