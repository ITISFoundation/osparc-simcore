""" database submodule associated to the postgres uservice

"""
import logging
import os
import socket
from typing import Optional

from aiopg.sa import Engine
from servicelib.common_aiopg_utils import DataSourceName, create_pg_engine
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.utils_aiopg import (
    close_engine,
    raise_if_migration_not_ready,
)
from tenacity import retry

from .config import POSTGRES_DB, POSTGRES_ENDPOINT, POSTGRES_PW, POSTGRES_USER

log = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(log).kwargs)
async def _ensure_pg_ready(dsn: DataSourceName, min_size: int, max_size: int) -> Engine:

    log.info("Creating pg engine for %s", dsn)

    engine = await create_pg_engine(dsn, minsize=min_size, maxsize=max_size)
    try:
        await raise_if_migration_not_ready(engine)
    except Exception:
        await close_engine(engine)
        raise

    return engine  # type: ignore # tenacity rules guarantee exit with exc


class DBContextManager:
    def __init__(self):
        self._db_engine: Optional[Engine] = None

    async def __aenter__(self):
        dsn = DataSourceName(
            application_name=f"{__name__}_{socket.gethostname()}_{os.getpid()}",
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PW,
            host=POSTGRES_ENDPOINT.split(":")[0],
            port=int(POSTGRES_ENDPOINT.split(":")[1]),
        )

        log.info("Creating pg engine for %s", dsn)
        engine = await _ensure_pg_ready(dsn, min_size=1, max_size=4)
        self._db_engine = engine
        return self._db_engine

    async def __aexit__(self, exc_type, exc, tb):
        assert self._db_engine is not None  # nosec

        if self._db_engine:
            await close_engine(self._db_engine)
            log.debug(
                "engine '%s' after shutdown: closed=%s, size=%d",
                self._db_engine.dsn,
                self._db_engine.closed,
                self._db_engine.size,
            )
