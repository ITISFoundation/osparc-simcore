import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.exceptions import HTTPException

from simcore_service_director_v2.modules import dynamic_services_v0

from ..api.entrypoints import api_router
from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.validation_error import http422_error_handler
from ..meta import api_version, api_vtag, project_name, summary
from ..modules import celery, db, director_v0, docker_registry, remote_debug
from ..utils.logging_utils import config_all_loggers
from .events import on_shutdown, on_startup
from .settings import AppSettings, BootModeEnum

logger = logging.getLogger(__name__)


def init_app(settings: Optional[AppSettings] = None) -> FastAPI:
    if settings is None:
        settings = AppSettings.create_from_env()

    logging.basicConfig(level=settings.loglevel)
    logging.root.setLevel(settings.loglevel)
    logger.debug(settings.json(indent=2))

    app = FastAPI(
        debug=settings.debug,
        title=project_name,
        description=summary,
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )

    app.state.settings = settings

    if settings.boot_mode == BootModeEnum.DEBUG:
        remote_debug.setup(app)

    if settings.director_v0.enabled:
        director_v0.setup(app, settings.director_v0)

    if settings.dynamic_services.enabled:
        dynamic_services_v0.setup(app, settings.dynamic_services)

    if settings.postgres.enabled:
        db.setup(app, settings.postgres)

    if settings.celery.enabled:
        celery.setup(app, settings.celery)

    if settings.registry.enabled:
        docker_registry.setup(app, settings.registry)

    # setup app --
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)

    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_http_error_handler_for_exception(
            status.HTTP_501_NOT_IMPLEMENTED, NotImplementedError
        ),
    )
    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR, Exception
        ),
    )

    app.include_router(api_router)

    config_all_loggers()

    return app
