from aiopg.sa.connection import SAConnection


class BaseRepository:
    """
        Repositories are pulled at every request
        All queries to db within that request use same connection
    """

    def __init__(self, conn: SAConnection) -> None:
        self._conn = conn

    @property
    def connection(self) -> SAConnection:
        return self._conn
