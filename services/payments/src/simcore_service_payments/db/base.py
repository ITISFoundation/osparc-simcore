from sqlalchemy.ext.asyncio import AsyncEngine


class BaseRepository:
    """
    Repositories are pulled at every request
    """

    def __init__(self, db_engine: AsyncEngine):
        assert db_engine is not None  # nosec
        self.db_engine = db_engine

    # FIXME:
    # async def transaction(self, connection: None) -> Iterable[]:
    #     if connection is not None:
    #         yield connection
    #     else:
    #         with self.db_engine.begin() as conn:
    #             yield conn
