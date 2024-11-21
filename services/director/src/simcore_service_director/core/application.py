import logging
from typing import Final

from fastapi import FastAPI
from servicelib.async_utils import cancel_sequential_workers
from servicelib.fastapi.tracing import setup_tracing

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
)
from ..api.rest.routes import setup_api_routes
from ..client_session import setup_client_session
from ..instrumentation import setup as setup_instrumentation
from ..registry_proxy import setup as setup_registry
from .settings import ApplicationSettings

_LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
_NOISY_LOGGERS: Final[tuple[str]] = ("werkzeug",)

_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> FastAPI:
    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + _LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    _logger.info("app settings: %s", settings.model_dump_json(indent=1))

    app = FastAPI(
        debug=settings.DIRECTOR_DEBUG,
        title=APP_NAME,
        description="Director-v0 service",
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    # STATE
    app.state.settings = settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    # PLUGINS SETUP
    setup_api_routes(app)

    if app.state.settings.DIRECTOR_TRACING:
        setup_tracing(app, app.state.settings.DIRECTOR_TRACING, APP_NAME)

    # replace by httpx client
    setup_client_session(app)
    setup_registry(app)

    setup_instrumentation(app)

    # ERROR HANDLERS

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        await cancel_sequential_workers()
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
