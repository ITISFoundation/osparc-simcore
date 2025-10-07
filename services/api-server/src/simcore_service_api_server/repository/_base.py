from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncEngine

DB_CACHE_TTL_SECONDS: Final = 120  # 2 minutes


@dataclass
class BaseRepository:
    """
    Repositories are pulled at every request
    """

    db_engine: AsyncEngine
