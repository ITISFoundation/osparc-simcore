""" database submodule associated to the postgres uservice

"""
import logging
import socket

import tenacity
from aiopg.sa import Engine
from servicelib.aiopg_utils import (
    DataSourceName,
    PostgresRetryPolicyUponInitialization,
    create_pg_engine,
    is_postgres_responsive,
)

from .config import POSTGRES_DB, POSTGRES_ENDPOINT, POSTGRES_PW, POSTGRES_USER

log = logging.getLogger(__name__)


@tenacity.retry(**PostgresRetryPolicyUponInitialization().kwargs)
async def wait_till_postgres_responsive(dsn: DataSourceName) -> None:
    if not is_postgres_responsive(dsn):
        raise Exception


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
        await wait_till_postgres_responsive(dsn)
        engine = await create_pg_engine(dsn, minsize=1, maxsize=4)
        self._db_engine = engine
        return self._db_engine

    async def __aexit__(self, exc_type, exc, tb):
        self._db_engine.close()
        await self._db_engine.wait_closed()
        log.debug(
            "engine '%s' after shutdown: closed=%s, size=%d",
            self._db_engine.dsn,
            self._db_engine.closed,
            self._db_engine.size,
        )
