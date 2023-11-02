from sqlalchemy.ext.asyncio import AsyncEngine


class BaseRepository:
    """
    Repositories are pulled at every request
    """

    def __init__(self, db_engine: AsyncEngine):
        assert db_engine is not None  # nosec
        self.db_engine = db_engine
