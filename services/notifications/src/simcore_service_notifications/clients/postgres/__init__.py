import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.logging_utils import log_context

from ._liveness import PostgresLiveness

_logger = logging.getLogger(__name__)


async def _postgres_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.postgres_liveness = PostgresLiveness(app)

    with log_context(_logger, logging.INFO, msg="setup postgres health"):
        await app.state.postgres_liveness.setup()

    yield {}

    with log_context(_logger, logging.INFO, msg="teardown postgres health"):
        await app.state.postgres_liveness.teardown()


def configure_postgres_liveness(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_postgres_lifespan)


def get_postgres_liveness(app: FastAPI) -> PostgresLiveness:
    assert isinstance(app.state.postgres_liveness, PostgresLiveness)  # nosec
    return app.state.postgres_liveness


__all__: tuple[str, ...] = ("PostgresLiveness",)
