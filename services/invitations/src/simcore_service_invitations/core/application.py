import logging

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.monitoring import configure_prometheus_instrumentation
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import configure_fastapi_app_tracing
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.routes import configure_rest_api
from . import exceptions_handlers
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    if settings.INVITATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_prometheus_instrumentation(app, app_lifespan)

    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(
            app,
            app_lifespan,
            tracing_config=tracing_config,
        )


def create_app(
    tracing_config: TracingConfig,
    settings: ApplicationSettings | None = None,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    if not settings:
        settings = ApplicationSettings.create_from_envs()
        _logger.info(
            "Application settings: %s",
            json_dumps(settings, indent=2, sort_keys=True),
        )

    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=APP_STARTED_BANNER_MSG,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            title=f"{PROJECT_NAME} web API",
            description=SUMMARY,
            version=API_VERSION,
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            docs_url="/dev/doc",
            redoc_url=None,  # default disabled, see below
            lifespan=app_lifespan,
        )
        override_fastapi_openapi_method(app)

        # STATE
        app.state.settings = settings
        app.state.tracing_config = tracing_config
        assert app.state.settings.API_VERSION == API_VERSION  # nosec

        _configure_plugins(app, app_lifespan, settings, tracing_config)

    configure_rest_api(app)

    exceptions_handlers.setup(app)

    return app
