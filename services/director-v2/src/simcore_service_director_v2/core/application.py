import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import setup_tracing
from starlette import status
from starlette.exceptions import HTTPException

from ..api.entrypoints import api_router
from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.validation_error import http422_error_handler
from ..meta import API_VERSION, API_VTAG, PROJECT_NAME, SUMMARY
from ..modules import (
    comp_scheduler,
    dask_clients_pool,
    db,
    director_v0,
    dynamic_services,
    dynamic_sidecar,
    rabbitmq,
    remote_debug,
    storage,
)
from ..utils.logging_utils import config_all_loggers
from .errors import (
    ClusterAccessForbiddenError,
    ClusterNotFoundError,
    PipelineNotFoundError,
    ProjectNotFoundError,
)
from .events import on_shutdown, on_startup
from .settings import AppSettings, BootModeEnum

logger = logging.getLogger(__name__)


def _set_exception_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    # director-v2 core.errors mappend into HTTP errors
    app.add_exception_handler(
        ProjectNotFoundError,
        make_http_error_handler_for_exception(
            status.HTTP_404_NOT_FOUND, ProjectNotFoundError
        ),
    )
    app.add_exception_handler(
        PipelineNotFoundError,
        make_http_error_handler_for_exception(
            status.HTTP_404_NOT_FOUND, PipelineNotFoundError
        ),
    )
    app.add_exception_handler(
        ClusterNotFoundError,
        make_http_error_handler_for_exception(
            status.HTTP_404_NOT_FOUND, ClusterNotFoundError
        ),
    )
    app.add_exception_handler(
        ClusterAccessForbiddenError,
        make_http_error_handler_for_exception(
            status.HTTP_403_FORBIDDEN, ClusterAccessForbiddenError
        ),
    )

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


def init_app(settings: Optional[AppSettings] = None) -> FastAPI:
    if settings is None:
        settings = AppSettings.create_from_envs()
    assert settings  # nosec
    logging.basicConfig(level=settings.LOG_LEVEL.value)
    logging.root.setLevel(settings.LOG_LEVEL.value)
    logger.debug(settings.json(indent=2))

    app = FastAPI(
        debug=settings.SC_BOOT_MODE
        in [BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL],
        title=PROJECT_NAME,
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )
    override_fastapi_openapi_method(app)

    app.state.settings = settings

    if settings.SC_BOOT_MODE == BootModeEnum.DEBUG:
        remote_debug.setup(app)

    if settings.DIRECTOR_V0.DIRECTOR_V0_ENABLED:
        director_v0.setup(app, settings.DIRECTOR_V0)

    if settings.DIRECTOR_V2_STORAGE:
        storage.setup(app, settings.DIRECTOR_V2_STORAGE)

    if settings.POSTGRES.DIRECTOR_V2_POSTGRES_ENABLED:
        db.setup(app, settings.POSTGRES)

    if settings.DYNAMIC_SERVICES.DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED:
        dynamic_services.setup(app, settings.DYNAMIC_SERVICES)

    if settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR and (
        settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        and settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED
    ):
        dynamic_sidecar.setup(app)

    if (
        settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED
    ):
        dask_clients_pool.setup(app, settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND)

    if settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_ENABLED:
        rabbitmq.setup(app)
        comp_scheduler.setup(app)

    if settings.DIRECTOR_V2_TRACING:
        setup_tracing(app, settings.DIRECTOR_V2_TRACING)

    # setup app --
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
    _set_exception_handlers(app)

    app.include_router(api_router)

    config_all_loggers()

    return app
