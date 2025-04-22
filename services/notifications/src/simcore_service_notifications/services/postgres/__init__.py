import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.fastapi.postgres_lifespan import PostgresLifespanState
from servicelib.logging_utils import log_context

from ._liveness import PostgresLiveness

_logger = logging.getLogger(__name__)


async def postgres_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
    app.state.engine = state[PostgresLifespanState.POSTGRES_ASYNC_ENGINE]

    app.state.postgres_health = PostgresLiveness(app)

    with log_context(_logger, logging.INFO, msg="setup postgres health"):
        await app.state.postgres_health.setup()

    yield {}

    with log_context(_logger, logging.INFO, msg="teardown postgres health"):
        await app.state.postgres_health.teardown()


def get_postgres_liveness(app: FastAPI) -> PostgresLiveness:
    assert isinstance(app.state.postgres_health, PostgresLiveness)  # nosec
    return app.state.postgres_health


__all__: tuple[str, ...] = ("PostgresLiveness",)
