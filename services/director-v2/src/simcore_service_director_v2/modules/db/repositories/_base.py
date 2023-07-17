from dataclasses import dataclass
from typing import TypeVar

from aiopg.sa import Engine

RepositoryType = TypeVar("RepositoryType", bound="BaseRepository")


@dataclass
class BaseRepository:
    """
    Repositories are pulled at every request
    """

    db_engine: Engine

    @classmethod
    def instance(cls: type[RepositoryType], db_engine: Engine) -> RepositoryType:
        return cls(db_engine=db_engine)
