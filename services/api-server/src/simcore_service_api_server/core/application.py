import logging

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi_pagination import add_pagination
from models_library.basic_types import BootModeEnum
from packaging.version import Version
from servicelib.fastapi.profiler import initialize_profiler
from servicelib.fastapi.tracing import (
    initialize_fastapi_app_tracing,
    setup_tracing,
)
from servicelib.tracing import TracingConfig

from .. import exceptions
from .._meta import API_VERSION, API_VTAG, APP_NAME
from ..api.root import create_router
from ..api.routes.health import router as health_router
from ..clients.celery_task_manager import setup_task_manager
from ..clients.postgres import setup_postgres
from ..services_http import director_v2, storage, webserver
from ..services_http.rabbitmq import setup_rabbitmq
from ._prometheus_instrumentation import setup_prometheus_instrumentation
from .events import on_shutdown, on_startup
from .openapi import override_openapi_method, use_route_names_as_operation_ids
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _label_title_and_version(settings: ApplicationSettings, title: str, version: str):
    labels = []
    if settings.API_SERVER_DEV_FEATURES_ENABLED:
        # builds public version identifier with pre: `[N!]N(.N)*[{a|b|rc}N][.postN][.devN]`
        # SEE https://packaging.python.org/en/latest/specifications/version-specifiers/#public-version-identifiers
        v = Version(version)
        version = f"{v.base_version}.post0.dev0"
        assert Version(version).is_devrelease, version  # nosec
        _logger.info("Setting up a developmental version: %s -> %s", v, version)

    if settings.debug:
        labels.append("debug")

    if local_version_label := "-".join(labels):
        # Appends local version identifier `<public version identifier>[+<local version label>]`
        # SEE https://packaging.python.org/en/latest/specifications/version-specifiers/#local-version-identifiers
        title += f" ({local_version_label})"
        version += f"+{local_version_label}"

    return title, version


def create_app(
    settings: ApplicationSettings | None = None,
    tracing_config: TracingConfig | None = None,
) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()
        _logger.info(
            "Application settings: %s",
            json_dumps(settings, indent=2, sort_keys=True),
        )
    if tracing_config is None:
        tracing_config = TracingConfig.create(
            service_name=APP_NAME, tracing_settings=settings.API_SERVER_TRACING
        )

    assert settings  # nosec
    assert tracing_config  # nosec

    # Labeling
    title = "osparc.io public API"
    version = API_VERSION  # public version identifier
    description = "osparc-simcore public API specifications"

    # Appends local version identifier if setup: version=<public version identifier>[+<local version label>]
    title, version = _label_title_and_version(settings, title, version)

    # creates app instance
    app = FastAPI(
        debug=settings.debug,
        title=title,
        description=description,
        version=version,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url="/doc",
    )
    override_openapi_method(app)
    add_pagination(app)

    app.state.settings = settings
    app.state.tracing_config = tracing_config

    if settings.API_SERVER_TRACING:
        setup_tracing(app, tracing_config)

    if settings.API_SERVER_POSTGRES:
        setup_postgres(app)

    setup_rabbitmq(app)

    if settings.API_SERVER_CELERY:
        setup_task_manager(app, settings.API_SERVER_CELERY)

    if app.state.settings.API_SERVER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    if settings.API_SERVER_TRACING:
        initialize_fastapi_app_tracing(
            app,
            tracing_config=tracing_config,
            add_response_trace_id_header=True,
        )

    if settings.API_SERVER_WEBSERVER:
        webserver.setup(
            app,
            settings.API_SERVER_WEBSERVER,
            tracing_settings=settings.API_SERVER_TRACING,
        )

    if settings.API_SERVER_STORAGE:
        storage.setup(
            app,
            settings.API_SERVER_STORAGE,
            tracing_settings=settings.API_SERVER_TRACING,
        )

    if settings.API_SERVER_DIRECTOR_V2:
        director_v2.setup(
            app,
            settings.API_SERVER_DIRECTOR_V2,
            tracing_settings=settings.API_SERVER_TRACING,
        )

    # setup app
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)

    if settings.API_SERVER_PROFILING:
        initialize_profiler(app)

    exceptions.setup_exception_handlers(
        app, is_debug=settings.SC_BOOT_MODE == BootModeEnum.DEBUG
    )

    # routing

    # healthcheck at / and at /VTAG/
    app.include_router(health_router)

    # api under /v*
    api_router = create_router(settings)
    app.include_router(api_router, prefix=f"/{API_VTAG}")

    # NOTE: cleanup all OpenAPIs https://github.com/ITISFoundation/osparc-simcore/issues/3487
    use_route_names_as_operation_ids(app)
    return app
