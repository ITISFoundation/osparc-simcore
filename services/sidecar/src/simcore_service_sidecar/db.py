""" database submodule associated to the postgres uservice

"""

import logging
import socket

from aiopg.sa import Engine
from tenacity import Retrying

from servicelib.aiopg_utils import (
    DataSourceName,
    PostgresRetryPolicyUponInitialization,
    create_pg_engine,
    raise_if_not_responsive,
)

from .config import POSTGRES_DB, POSTGRES_ENDPOINT, POSTGRES_PW, POSTGRES_USER

log = logging.getLogger(__name__)


class DBContextManager:
    def __init__(self):
        self._db_engine: Engine = None

    async def __aenter__(self):
        dsn = DataSourceName(
            application_name=f"{__name__}_{id(socket.gethostname())}",
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PW,
            host=POSTGRES_ENDPOINT.split(":")[0],
            port=POSTGRES_ENDPOINT.split(":")[1],
        )

        log.info("Creating pg engine for %s", dsn)
        for attempt in Retrying(**PostgresRetryPolicyUponInitialization(log).kwargs):
            with attempt:
                engine = await create_pg_engine(dsn, minsize=1, maxsize=4)
                await raise_if_not_responsive(engine)

        self._db_engine = engine
        return self._db_engine

    async def __aexit__(self, exc_type, exc, tb):
        self._db_engine.close()
        await self._db_engine.wait_closed()
        assert self._db_engine.closed
        log.debug(
            "engine '%s' after shutdown: closed=%s, size=%d",
            self._db_engine.dsn,
            self._db_engine.closed,
            self._db_engine.size,
        )
