import logging
from typing import Final

from common_library.json_serialization import json_dumps
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.lifespan_utils import Lifespan
from servicelib.fastapi.logging_lifespan import create_logging_shutdown_event
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.profiler import configure_profiler
from servicelib.fastapi.tracing import (
    get_tracing_config,
    initialize_fastapi_app_tracing,
    setup_tracing,
)
from servicelib.tracing import TracingConfig

from .._meta import API_VERSION, API_VTAG, APP_NAME, PROJECT_NAME, SUMMARY
from ..api.entrypoints import setup_api_routes
from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.validation_error import http422_error_handler
from ..api.rpc.routes import setup_rpc_api_routes
from ..modules import (
    catalog,
    comp_scheduler,
    dask_clients_pool,
    db,
    director_v0,
    dynamic_services,
    dynamic_sidecar,
    instrumentation,
    long_running_tasks,
    notifier,
    rabbitmq,
    redis,
    resource_usage_tracker_client,
    socketio,
    storage,
)
from ..modules.osparc_variables import substitutions
from .errors import (
    ClusterNotFoundError,
    ComputationalRunNotFoundError,
    PipelineNotFoundError,
    ProjectNetworkNotFoundError,
    ProjectNotFoundError,
)
from .events import on_shutdown, on_startup
from .settings import AppSettings

_logger = logging.getLogger(__name__)

_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "httpcore",
    "httpx",
)


def _set_exception_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    # director-v2 core.errors mappend into HTTP errors
    app.add_exception_handler(
        ProjectNotFoundError,
        make_http_error_handler_for_exception(status.HTTP_404_NOT_FOUND, ProjectNotFoundError),
    )
    app.add_exception_handler(
        ProjectNetworkNotFoundError,
        make_http_error_handler_for_exception(status.HTTP_404_NOT_FOUND, ProjectNetworkNotFoundError),
    )
    app.add_exception_handler(
        PipelineNotFoundError,
        make_http_error_handler_for_exception(status.HTTP_404_NOT_FOUND, PipelineNotFoundError),
    )
    app.add_exception_handler(
        ClusterNotFoundError,
        make_http_error_handler_for_exception(status.HTTP_404_NOT_FOUND, ClusterNotFoundError),
    )
    app.add_exception_handler(
        ComputationalRunNotFoundError,
        make_http_error_handler_for_exception(status.HTTP_404_NOT_FOUND, ComputationalRunNotFoundError),
    )

    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_http_error_handler_for_exception(status.HTTP_501_NOT_IMPLEMENTED, NotImplementedError),
    )
    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(status.HTTP_500_INTERNAL_SERVER_ERROR, Exception),
    )


def create_app_lifespan(logging_lifespan: Lifespan | None = None) -> LifespanManager:
    app_lifespan = LifespanManager()
    if logging_lifespan:
        app_lifespan.add(logging_lifespan)
    return app_lifespan


def create_base_app(
    app_settings: AppSettings | None = None,
) -> FastAPI:
    if app_settings is None:
        app_settings = AppSettings.create_from_envs()

    tracing_config = TracingConfig.create(service_name=APP_NAME, tracing_settings=app_settings.DIRECTOR_V2_TRACING)
    logging_shutdown_event = create_logging_shutdown_event(
        log_format_local_dev_enabled=app_settings.DIRECTOR_V2_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=app_settings.DIRECTOR_V2_LOG_FILTER_MAPPING,
        tracing_config=tracing_config,
        log_base_level=app_settings.log_level,
        noisy_loggers=_NOISY_LOGGERS,
    )

    _logger.info(
        "Application settings: %s",
        json_dumps(app_settings, indent=2, sort_keys=True),
    )

    assert app_settings  # nosec

    assert app_settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=app_settings.SC_BOOT_MODE.is_devel_mode(),
        title=PROJECT_NAME,
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        **get_common_oas_options(is_devel_mode=app_settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = app_settings
    app.state.tracing_config = tracing_config

    setup_api_routes(app)

    app.add_event_handler("shutdown", logging_shutdown_event)

    return app


def _setup_tracing_if_enabled(app: FastAPI) -> None:
    if get_tracing_config(app).tracing_enabled:
        setup_tracing(app, get_tracing_config(app))


def _setup_external_service_clients(app: FastAPI, settings: AppSettings) -> None:
    if settings.DIRECTOR_V0.DIRECTOR_ENABLED:
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


def _is_dynamic_scheduler_enabled(settings: AppSettings) -> bool:
    return bool(
        settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        and settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        and settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED
    )


def _setup_rabbitmq_and_redis(
    app: FastAPI, *, dynamic_scheduler_enabled: bool, computational_backend_enabled: bool
) -> None:
    if dynamic_scheduler_enabled or computational_backend_enabled:
        rabbitmq.setup(app)
        setup_rpc_api_routes(app)  # Requires rabbitmq to be setup first
        redis.setup(app)


def _setup_dynamic_scheduler_modules(app: FastAPI) -> None:
    dynamic_sidecar.setup(app)
    socketio.setup(app)
    notifier.setup(app)
    long_running_tasks.setup(app)


def _setup_computational_backend(app: FastAPI, settings: AppSettings, *, computational_backend_enabled: bool) -> None:
    if settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED:
        dask_clients_pool.setup(app, settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND)

    if computational_backend_enabled:
        comp_scheduler.setup(app)


def create_app(
    settings: AppSettings | None = None,
) -> FastAPI:
    # base app + settings
    app = create_base_app(settings)
    if settings is None:
        settings = app.state.settings
        _logger.info(
            "Application settings: %s",
            json_dumps(settings, indent=2, sort_keys=True),
        )
    assert settings is not None  # nosec

    # osparc variables & tracing
    substitutions.setup(app)
    _setup_tracing_if_enabled(app)

    # instrumentation
    if settings.DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED:
        instrumentation.setup(app)

    # external service clients (director-v0, storage, catalog)
    _setup_external_service_clients(app, settings)

    # database
    db.setup(
        app,
        settings.POSTGRES,
        tracing_config=get_tracing_config(app),
        monitoring_enabled=settings.DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED,
    )

    if get_tracing_config(app).tracing_enabled:
        initialize_fastapi_app_tracing(app, tracing_config=get_tracing_config(app))

    # dynamic services
    if settings.DYNAMIC_SERVICES.DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED:
        dynamic_services.setup(app)

    dynamic_scheduler_enabled = _is_dynamic_scheduler_enabled(settings)
    computational_backend_enabled = settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_ENABLED

    # messaging backends (rabbitmq, rpc routes, redis)
    _setup_rabbitmq_and_redis(
        app,
        dynamic_scheduler_enabled=dynamic_scheduler_enabled,
        computational_backend_enabled=computational_backend_enabled,
    )

    # dynamic sidecar scheduler
    if dynamic_scheduler_enabled:
        _setup_dynamic_scheduler_modules(app)

    # computational backend (dask client, scheduler)
    _setup_computational_backend(app, settings, computational_backend_enabled=computational_backend_enabled)

    # resource usage tracker
    resource_usage_tracker_client.setup(app)

    # profiling
    if settings.DIRECTOR_V2_PROFILING:
        configure_profiler(app)

    # event handlers & exception handlers
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
    _set_exception_handlers(app)

    return app
