from collections.abc import AsyncIterator
from typing import Final

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.logging_lifespan import create_logging_lifespan
from servicelib.fastapi.monitoring import (
    create_prometheus_instrumentationmain_input_state,
    prometheus_instrumentation_lifespan,
)
from servicelib.tracing import TracingConfig

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from .settings import ApplicationSettings

_NOISY_LOGGERS: Final[tuple[str, ...]] = ()


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
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> LifespanManager[FastAPI]:
    # WARNING: order matters
    app_lifespan = LifespanManager()
    app_lifespan.add(
        create_logging_lifespan(
            log_format_local_dev_enabled=settings.INVITATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED,
            logger_filter_mapping=settings.INVITATIONS_LOG_FILTER_MAPPING,
            tracing_config=tracing_config,
            log_base_level=settings.log_level,
            noisy_loggers=_NOISY_LOGGERS,
        )
    )
    app_lifespan.add(_settings_lifespan)

    # - prometheus instrumentation
    app_lifespan.add(prometheus_instrumentation_lifespan)

    app_lifespan.add(_app_banner_lifespan)

    return app_lifespan
