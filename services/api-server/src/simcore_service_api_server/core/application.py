import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from ..meta import api_version, api_vtag
from ..api.errors.http_error import http_error_handler
from ..api.errors.validation_error import http422_error_handler
from ..api.root import router as api_router
from ..api.routes.health import router as health_router
from ..modules import catalog, remote_debug, webserver, storage, director
from .events import create_start_app_handler, create_stop_app_handler
from .openapi import override_openapi_method, use_route_names_as_operation_ids
from .redoc import create_redoc_handler
from .settings import AppSettings, BootModeEnum

logger = logging.getLogger(__name__)


def init_app(settings: Optional[AppSettings] = None) -> FastAPI:
    if settings is None:
        settings = AppSettings.create_from_env()

    logging.basicConfig(level=settings.loglevel)
    logging.root.setLevel(settings.loglevel)
    logger.debug(settings)

    # creates app instance
    app = FastAPI(
        debug=settings.debug,
        title="Public API Server",
        description="osparc-simcore Public RESTful API Specifications",
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
    )
    override_openapi_method(app)

    app.state.settings = settings

    # setup modules
    if settings.boot_mode == BootModeEnum.DEBUG:
        remote_debug.setup(app)

    if settings.webserver.enabled:
        webserver.setup(app, settings.webserver)

    if settings.catalog.enabled:
        catalog.setup(app, settings.catalog)

    if settings.storage.enabled:
        storage.setup(app, settings.storage)

    if settings.director.enabled:
        director.setup(app, settings.director)


    # setup app
    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))

    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)

    # routing

    # healthcheck at / and at /v0/
    app.include_router(health_router)

    # docs
    redoc_html = create_redoc_handler(app)
    app.add_route("/doc", redoc_html, include_in_schema=False)

    # api under /v*
    app.include_router(api_router, prefix=f"/{api_vtag}")

    use_route_names_as_operation_ids(app)

    return app
