import logging
from collections.abc import AsyncIterator, Iterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanState,
    postgres_database_lifespan,
)
from servicelib.logging_utils import log_context

from ...repositories import UserPreferencesRepository
from ._liveness import PostgresLiveness

_logger = logging.getLogger(__name__)


postgres_lifespan_manager = LifespanManager()
postgres_lifespan_manager.add(postgres_database_lifespan)


@postgres_lifespan_manager.add
async def _postgres_liveness_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
    async_engine = state[PostgresLifespanState.POSTGRES_ASYNC_ENGINE]

    app.state.postgres_liveness = PostgresLiveness(async_engine)

    with log_context(_logger, logging.INFO, msg="setup postgres health"):
        await app.state.postgres_liveness.setup()

    yield {}

    with log_context(_logger, logging.INFO, msg="teardown postgres health"):
        await app.state.postgres_liveness.teardown()


@postgres_lifespan_manager.add
def _repositories_lifespan(app: FastAPI, state: State) -> Iterator[State]:
    async_engine = state[PostgresLifespanState.POSTGRES_ASYNC_ENGINE]

    app.state.repositories = {
        UserPreferencesRepository.__name__: UserPreferencesRepository(async_engine),
    }

    yield {}


def get_postgres_liveness(app: FastAPI) -> PostgresLiveness:
    assert isinstance(app.state.postgres_liveness, PostgresLiveness)  # nosec
    return app.state.postgres_liveness


def get_repository[T](app: FastAPI, repo_class: type[T]) -> T:
    repo = app.state.repositories[repo_class.__name__]
    assert isinstance(repo, repo_class)  # nosec
    return repo
