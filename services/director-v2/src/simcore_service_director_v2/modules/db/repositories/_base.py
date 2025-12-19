from dataclasses import dataclass
from typing import Self, TypeVar

from sqlalchemy.ext.asyncio import AsyncEngine

RepositoryType = TypeVar("RepositoryType", bound="BaseRepository")


@dataclass
class BaseRepository:
    """
    Repositories are pulled at every request
    """

    db_engine: AsyncEngine

    @classmethod
    def instance(cls, db_engine: AsyncEngine) -> Self:
        return cls(db_engine=db_engine)
