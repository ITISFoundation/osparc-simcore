import logging

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from fastapi_pagination import add_pagination
from models_library.basic_types import BootModeEnum
from packaging.version import Version
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.profiler import configure_profiler
from servicelib.fastapi.tracing import (
    configure_fastapi_app_tracing,
)
from servicelib.tracing import TracingConfig

from .. import exceptions
from .._locale_middleware import LocaleMiddleware
from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
)
from ..api.root import create_router
from ..api.routes.health import router as health_router
from ..clients.celery_task_manager import configure_task_manager
from ..clients.kms import configure_kms
from ..clients.postgres import configure_postgres
from ..services_http import director_v2, storage, webserver
from ..services_http.chatbot import configure as configure_chatbot
from ..services_http.rabbitmq import configure_rabbitmq
from ._prometheus_instrumentation import configure_api_server_prometheus_instrumentation
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


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(
            app,
            app_lifespan,
            tracing_config=tracing_config,
            add_response_trace_id_header=True,
        )

    if settings.API_SERVER_POSTGRES:
        configure_postgres(app_lifespan, tracing_config=tracing_config)

    configure_rabbitmq(app_lifespan)

    if settings.API_SERVER_CELERY:
        configure_task_manager(app_lifespan, settings.API_SERVER_CELERY)

    configure_kms(app_lifespan)

    if settings.API_SERVER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_api_server_prometheus_instrumentation(app, app_lifespan)

    if settings.API_SERVER_CHATBOT:
        configure_chatbot(
            app,
            app_lifespan,
            base_url=str(settings.API_SERVER_CHATBOT.CHATBOT_URL),
            tracing_settings=settings.API_SERVER_TRACING,
        )

    if settings.API_SERVER_WEBSERVER:
        webserver.configure(
            app,
            app_lifespan,
            settings.API_SERVER_WEBSERVER,
            tracing_settings=settings.API_SERVER_TRACING,
        )

    if settings.API_SERVER_STORAGE:
        storage.configure(
            app,
            app_lifespan,
            settings.API_SERVER_STORAGE,
            tracing_settings=settings.API_SERVER_TRACING,
        )

    if settings.API_SERVER_DIRECTOR_V2:
        director_v2.configure(
            app,
            app_lifespan,
            settings.API_SERVER_DIRECTOR_V2,
            tracing_settings=settings.API_SERVER_TRACING,
        )


def create_app(
    settings: ApplicationSettings | None = None,
    tracing_config: TracingConfig | None = None,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()
        _logger.info(
            "Application settings: %s",
            json_dumps(settings, indent=2, sort_keys=True),
        )
    if tracing_config is None:
        tracing_config = TracingConfig.create(service_name=APP_NAME, tracing_settings=settings.API_SERVER_TRACING)

    assert settings  # nosec
    assert tracing_config  # nosec

    # Labeling
    title = "osparc.io public API"
    version = API_VERSION  # public version identifier
    description = "osparc-simcore public API specifications"

    # Appends local version identifier if setup: version=<public version identifier>[+<local version label>]
    title, version = _label_title_and_version(settings, title, version)

    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=APP_STARTED_BANNER_MSG,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            debug=settings.debug,
            title=title,
            description=description,
            version=version,
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            docs_url="/dev/doc",
            redoc_url="/doc",
            lifespan=app_lifespan,
        )
        override_openapi_method(app)
        add_pagination(app)

        app.state.settings = settings
        app.state.tracing_config = tracing_config

        _configure_plugins(app, app_lifespan, settings, tracing_config)

    if settings.API_SERVER_PROFILING:
        configure_profiler(app)

    if settings.API_SERVER_LOCALIZED_MESSAGES_ENABLED:
        app.add_middleware(LocaleMiddleware)

    exceptions.setup_exception_handlers(app, is_debug=settings.SC_BOOT_MODE == BootModeEnum.DEBUG)

    # routing

    # healthcheck at / and at /VTAG/
    app.include_router(health_router)

    # api under /v*
    api_router = create_router(settings)
    app.include_router(api_router, prefix=f"/{API_VTAG}")

    # NOTE: cleanup all OpenAPIs https://github.com/ITISFoundation/osparc-simcore/issues/3487
    use_route_names_as_operation_ids(app)
    return app
