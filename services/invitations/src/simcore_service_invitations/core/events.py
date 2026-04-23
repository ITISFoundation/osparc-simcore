from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.lifespan_utils import Lifespan
from servicelib.fastapi.monitoring import (
    create_prometheus_instrumentationmain_input_state,
    prometheus_instrumentation_lifespan,
)

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from .settings import ApplicationSettings


async def _app_banner_lifespan(app: FastAPI) -> AsyncIterator[State]:
    assert app  # nosec
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _settings_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    yield {
        **create_prometheus_instrumentationmain_input_state(
            enabled=settings.INVITATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED
        ),
    }


def create_app_lifespan(
    logging_lifespan: Lifespan | None = None,
) -> LifespanManager[FastAPI]:
    # WARNING: order matters
    app_lifespan = LifespanManager()
    if logging_lifespan:
        app_lifespan.add(logging_lifespan)
    app_lifespan.add(_settings_lifespan)

    # - prometheus instrumentation
    app_lifespan.add(prometheus_instrumentation_lifespan)

    app_lifespan.add(_app_banner_lifespan)

    return app_lifespan
