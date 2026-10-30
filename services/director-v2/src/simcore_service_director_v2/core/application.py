import logging
from typing import Final

from common_library.json_serialization import json_dumps
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.logging_lifespan import create_logging_lifespan
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.fastapi.profiler import configure_profiler
from servicelib.fastapi.tracing import configure_fastapi_app_tracing, get_tracing_config
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.entrypoints import setup_api_routes
from ..api.errors.http_error import (
    http_error_handler,
    make_http_error_handler_for_exception,
)
from ..api.errors.validation_error import http422_error_handler
from ..api.rpc.routes import configure_rpc_api_routes
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


def _is_dynamic_scheduler_enabled(settings: AppSettings) -> bool:
    return bool(
        settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        and settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        and settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED
    )


def _configure_external_service_clients(app_lifespan: LifespanManager, settings: AppSettings) -> None:
    if settings.DIRECTOR_V0.DIRECTOR_ENABLED:
        director_v0.configure_director_v0(
            app_lifespan,
            director_v0_settings=settings.DIRECTOR_V0,
            tracing_settings=settings.DIRECTOR_V2_TRACING,
        )

    if settings.DIRECTOR_V2_STORAGE:
        storage.configure_storage(
            app_lifespan,
            storage_settings=settings.DIRECTOR_V2_STORAGE,
            tracing_settings=settings.DIRECTOR_V2_TRACING,
        )

    if settings.DIRECTOR_V2_CATALOG:
        catalog.configure_catalog(
            app_lifespan,
            catalog_settings=settings.DIRECTOR_V2_CATALOG,
            tracing_settings=settings.DIRECTOR_V2_TRACING,
        )


def _configure_rabbitmq_and_redis(
    app_lifespan: LifespanManager,
    settings: AppSettings,
    *,
    dynamic_scheduler_enabled: bool,
    computational_backend_enabled: bool,
) -> None:
    if dynamic_scheduler_enabled or computational_backend_enabled:
        rabbitmq.configure_rabbitmq(app_lifespan, settings=settings.DIRECTOR_V2_RABBITMQ)
        configure_rpc_api_routes(app_lifespan)  # Requires rabbitmq to be setup first
        redis.configure_redis(app_lifespan, settings=settings.REDIS)


def _configure_dynamic_scheduler_modules(app: FastAPI, app_lifespan: LifespanManager) -> None:
    dynamic_sidecar.configure_dynamic_sidecar(app, app_lifespan)
    socketio.configure_socketio(app_lifespan)
    notifier.configure_notifier(app_lifespan)
    long_running_tasks.configure_long_running_tasks(app_lifespan)


def _configure_computational_backend(
    app_lifespan: LifespanManager, settings: AppSettings, *, computational_backend_enabled: bool
) -> None:
    if settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED:
        dask_clients_pool.configure_dask_clients_pool(app_lifespan, settings=settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND)

    if computational_backend_enabled:
        comp_scheduler.configure_comp_scheduler(app_lifespan)


def _configure_plugins(app: FastAPI, app_lifespan: LifespanManager, settings: AppSettings) -> None:
    # osparc variables
    substitutions.configure_substitutions(app_lifespan)

    # tracing
    if get_tracing_config(app).tracing_enabled:
        configure_fastapi_app_tracing(app, app_lifespan, tracing_config=get_tracing_config(app))

    # instrumentation
    if settings.DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED:
        instrumentation.configure_instrumentation(app, app_lifespan)

    # external service clients (director-v0, storage, catalog)
    _configure_external_service_clients(app_lifespan, settings)

    # database
    db.configure_db(
        app_lifespan,
        settings=settings.POSTGRES,
        tracing_config=get_tracing_config(app),
        monitoring_enabled=settings.DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED,
    )

    # dynamic services
    if settings.DYNAMIC_SERVICES.DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED:
        dynamic_services.configure_dynamic_services(app_lifespan)

    dynamic_scheduler_enabled = _is_dynamic_scheduler_enabled(settings)
    computational_backend_enabled = settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_ENABLED

    # messaging backends (rabbitmq, rpc routes, redis)
    _configure_rabbitmq_and_redis(
        app_lifespan,
        settings,
        dynamic_scheduler_enabled=dynamic_scheduler_enabled,
        computational_backend_enabled=computational_backend_enabled,
    )

    # dynamic sidecar scheduler
    if dynamic_scheduler_enabled:
        _configure_dynamic_scheduler_modules(app, app_lifespan)

    # computational backend (dask client, scheduler)
    _configure_computational_backend(
        app_lifespan, settings, computational_backend_enabled=computational_backend_enabled
    )

    # resource usage tracker
    resource_usage_tracker_client.configure_resource_usage_tracker_client(app_lifespan)

    # profiling
    if settings.DIRECTOR_V2_PROFILING:
        configure_profiler(app)


def create_base_app(
    app_settings: AppSettings,
    tracing_config: TracingConfig,
    app_lifespan: LifespanManager,
) -> FastAPI:
    assert app_settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=app_settings.SC_BOOT_MODE.is_devel_mode(),
        title=PROJECT_NAME,
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        lifespan=app_lifespan,
        **get_common_oas_options(is_devel_mode=app_settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = app_settings
    app.state.tracing_config = tracing_config

    setup_api_routes(app)

    return app


def create_app(
    settings: AppSettings | None = None,
    *,
    tracing_config: TracingConfig | None = None,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    if settings is None:
        settings = AppSettings.create_from_envs()
        _logger.info(
            "Application settings: %s",
            json_dumps(settings, indent=2, sort_keys=True),
        )

    if tracing_config is None:
        tracing_config = TracingConfig.create(service_name=APP_NAME, tracing_settings=settings.DIRECTOR_V2_TRACING)

    if logging_lifespan is None:
        logging_lifespan = create_logging_lifespan(
            log_format_local_dev_enabled=settings.DIRECTOR_V2_LOG_FORMAT_LOCAL_DEV_ENABLED,
            logger_filter_mapping=settings.DIRECTOR_V2_LOG_FILTER_MAPPING,
            tracing_config=tracing_config,
            log_base_level=settings.logging_level,
            noisy_loggers=_NOISY_LOGGERS,
        )

    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=APP_STARTED_BANNER_MSG,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = create_base_app(settings, tracing_config, app_lifespan)
        _configure_plugins(app, app_lifespan, settings)

    _set_exception_handlers(app)

    return app
