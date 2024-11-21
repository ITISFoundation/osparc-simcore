import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.profiler_middleware import ProfilerMiddleware
from servicelib.fastapi.tracing import setup_tracing
from servicelib.logging_utils import config_all_loggers

from .._meta import API_VERSION, API_VTAG, APP_NAME, PROJECT_NAME, SUMMARY
from ..api.entrypoints import api_router
from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.validation_error import http422_error_handler
from ..modules import (
    catalog,
    comp_scheduler,
    dask_clients_pool,
    db,
    director_v0,
    dynamic_services,
    dynamic_sidecar,
    instrumentation,
    notifier,
    rabbitmq,
    redis,
    resource_usage_tracker_client,
    socketio,
    storage,
)
from ..modules.osparc_variables import substitutions
from .errors import (
    ClusterAccessForbiddenError,
    ClusterNotFoundError,
    PipelineNotFoundError,
    ProjectNetworkNotFoundError,
    ProjectNotFoundError,
)
from .events import on_shutdown, on_startup
from .settings import AppSettings

_logger = logging.getLogger(__name__)


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
        ProjectNetworkNotFoundError,
        make_http_error_handler_for_exception(
            status.HTTP_404_NOT_FOUND, ProjectNetworkNotFoundError
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


_LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
_NOISY_LOGGERS = (
    "aio_pika",
    "aiormq",
    "httpcore",
)


def create_base_app(settings: AppSettings | None = None) -> FastAPI:
    if settings is None:
        settings = AppSettings.create_from_envs()
    assert settings  # nosec

    logging.basicConfig(level=settings.LOG_LEVEL.value)
    logging.root.setLevel(settings.LOG_LEVEL.value)
    config_all_loggers(
        log_format_local_dev_enabled=settings.DIRECTOR_V2_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.DIRECTOR_V2_LOG_FILTER_MAPPING,
    )
    _logger.debug(settings.model_dump_json(indent=2))

    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + _LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    assert settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=settings.SC_BOOT_MODE.is_devel_mode(),
        title=PROJECT_NAME,
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        **get_common_oas_options(is_devel_mode=settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = settings

    app.include_router(api_router)
    return app


def init_app(settings: AppSettings | None = None) -> FastAPI:
    app = create_base_app(settings)
    if settings is None:
        settings = app.state.settings
    assert settings  # nosec

    substitutions.setup(app)

    if settings.DIRECTOR_V2_TRACING:
        setup_tracing(app, settings.DIRECTOR_V2_TRACING, APP_NAME)

    if settings.DIRECTOR_V0.DIRECTOR_V0_ENABLED:
        director_v0.setup(
            app,
            director_v0_settings=settings.DIRECTOR_V0,
            tracing_settings=settings.DIRECTOR_V2_TRACING,
        )

    if settings.DIRECTOR_V2_STORAGE:
        storage.setup(
            app,
            storage_settings=settings.DIRECTOR_V2_STORAGE,
            tracing_settings=settings.DIRECTOR_V2_TRACING,
        )

    if settings.DIRECTOR_V2_CATALOG:
        catalog.setup(
            app,
            catalog_settings=settings.DIRECTOR_V2_CATALOG,
            tracing_settings=settings.DIRECTOR_V2_TRACING,
        )

    db.setup(app, settings.POSTGRES)

    if settings.DYNAMIC_SERVICES.DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED:
        dynamic_services.setup(app, tracing_settings=settings.DIRECTOR_V2_TRACING)

    dynamic_scheduler_enabled = settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR and (
        settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        and settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED
    )

    computational_backend_enabled = (
        settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_ENABLED
    )
    if dynamic_scheduler_enabled or computational_backend_enabled:
        rabbitmq.setup(app)
        redis.setup(app)

    if dynamic_scheduler_enabled:
        dynamic_sidecar.setup(app)
        socketio.setup(app)
        notifier.setup(app)

    if (
        settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED
    ):
        dask_clients_pool.setup(app, settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND)

    if computational_backend_enabled:
        comp_scheduler.setup(app)

    resource_usage_tracker_client.setup(app)

    if settings.DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED:
        instrumentation.setup(app)

    if settings.DIRECTOR_V2_PROFILING:
        app.add_middleware(ProfilerMiddleware)

    # setup app --
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
    _set_exception_handlers(app)

    return app
