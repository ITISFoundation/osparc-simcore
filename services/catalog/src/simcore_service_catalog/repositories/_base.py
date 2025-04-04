from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class BaseRepository:
    """
    Repositories are pulled at every request
    """

    db_engine: AsyncEngine
