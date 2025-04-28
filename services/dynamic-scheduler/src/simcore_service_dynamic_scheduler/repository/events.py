import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanState,
    postgres_database_lifespan,
)

from .project_networks import ProjectNetworksRepo

_logger = logging.getLogger(__name__)


async def _database_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
    app.state.engine = state[PostgresLifespanState.POSTGRES_ASYNC_ENGINE]

    app.state.repositories = {
        ProjectNetworksRepo.__name__: ProjectNetworksRepo(app.state.engine),
    }

    yield {}


repository_lifespan_manager = LifespanManager()
repository_lifespan_manager.add(postgres_database_lifespan)
repository_lifespan_manager.add(_database_lifespan)


def get_project_networks_repo(app: FastAPI) -> ProjectNetworksRepo:
    assert isinstance(app.state.repositories, dict)  # nosec
    repo = app.state.repositories.get(ProjectNetworksRepo.__name__)
    assert isinstance(repo, ProjectNetworksRepo)  # nosec
    return repo
