from dataclasses import dataclass

from aiopg.sa import Engine


@dataclass
class BaseRepository:
    """
    Repositories are pulled at every request
    """

    db_engine: Engine = None
