import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.fastapi.postgres_lifespan import PostgresLifespanState
from servicelib.logging_utils import log_context

from ...core.settings import ApplicationSettings
from ._health import PostgresHealth

_logger = logging.getLogger(__name__)


async def postgres_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
    app.state.engine = state[PostgresLifespanState.POSTGRES_ASYNC_ENGINE]

    app.state.postgres_health = PostgresHealth(app)

    with log_context(_logger, logging.INFO, msg="setup postgres health"):
        await app.state.postgres_health.setup()

    yield {}

    with log_context(_logger, logging.INFO, msg="teardown postgres health"):
        await app.state.postgres_health.teardown()


def get_postgres_health(app: FastAPI) -> PostgresHealth:
    assert isinstance(app.state.postgres_health, PostgresHealth)  # nosec
    return app.state.postgres_health


__all__: tuple[str, ...] = ("PostgresHealth",)
