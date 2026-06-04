from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.httpx_client import create_httpx_settings_state, httpx_lifespan
from servicelib.fastapi.lifespan_utils import Lifespan

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..modules.docker_registry import registry_lifespan
from .settings import ApplicationSettings


async def _banners_lifespan(_) -> AsyncIterator[State]:
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _settings_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings

    yield {
        **create_httpx_settings_state(
            max_keepalive_connections=settings.DIRECTOR_REGISTRY_CLIENT_MAX_KEEPALIVE_CONNECTIONS,
            default_timeout=settings.DIRECTOR_REGISTRY_CLIENT_TIMEOUT,
        ),
    }


def create_app_lifespan(logging_lifespan: Lifespan | None = None) -> LifespanManager:  # WARNING: order matters
    app_lifespan = LifespanManager()
    if logging_lifespan:
        app_lifespan.add(logging_lifespan)

    app_lifespan.add(_settings_lifespan)

    app_lifespan.add(
        httpx_lifespan
    )  # WARNING: httpx client should be started before any other lifespan that needs it, e.g. registry

    app_lifespan.add(registry_lifespan)

    # last one
    app_lifespan.add(_banners_lifespan)

    return app_lifespan
