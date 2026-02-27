from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanState,
    postgres_database_lifespan,
)

from ..services import p_scheduler
from .project_networks import ProjectNetworksRepo


async def _database_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
    app.state.engine = state[PostgresLifespanState.POSTGRES_ASYNC_ENGINE]

    app.state.repositories = {
        ProjectNetworksRepo.__name__: ProjectNetworksRepo(app.state.engine),
        **{repo.__name__: repo(app.state.engine) for repo in p_scheduler.repositories},
    }

    yield {}


repository_lifespan_manager = LifespanManager()
repository_lifespan_manager.add(postgres_database_lifespan)
repository_lifespan_manager.add(_database_lifespan)
