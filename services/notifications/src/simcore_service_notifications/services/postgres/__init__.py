import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.fastapi.db_asyncpg_engine import (
    close_db_connection,
    connect_to_db,
)
from servicelib.fastapi.postgres_lifespan import PostgresLifespanState
from servicelib.logging_utils import log_context

from ...core.settings import ApplicationSettings
from ._health import PostgresHealth

_logger = logging.getLogger(__name__)


async def postgres_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
    app.state.engine = state[PostgresLifespanState.POSTGRES_ASYNC_ENGINE]

    settings: ApplicationSettings = app.state.settings

    app.state.postgress_liveness = PostgresHealth(app)

    with log_context(_logger, logging.INFO, msg="connecting to postgres"):
        await connect_to_db(app, settings.NOTIFICATIONS_POSTGRES)
        await app.state.postgress_liveness.setup()

    yield {}

    with log_context(_logger, logging.INFO, msg="disconnecting from postgres"):
        await app.state.postgress_liveness.teardown()
        await close_db_connection(app)


def get_postgress_health(app: FastAPI) -> PostgresHealth:
    assert isinstance(app.state.postgress_liveness, PostgresHealth)  # nosec
    return app.state.postgress_liveness


__all__: tuple[str, ...] = ("PostgresHealth",)
