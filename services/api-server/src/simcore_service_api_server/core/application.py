import logging

from fastapi import FastAPI
from fastapi_pagination import add_pagination
from models_library.basic_types import BootModeEnum
from packaging.version import Version
from servicelib.fastapi.profiler_middleware import ProfilerMiddleware
from servicelib.fastapi.tracing import setup_tracing
from servicelib.logging_utils import config_all_loggers

from .. import exceptions
from .._meta import API_VERSION, API_VTAG, APP_NAME
from ..api.root import create_router
from ..api.routes.health import router as health_router
from ..services import catalog, director_v2, storage, webserver
from ..services.rabbitmq import setup_rabbitmq
from ._prometheus_instrumentation import setup_prometheus_instrumentation
from .events import create_start_app_handler, create_stop_app_handler
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


def init_app(settings: ApplicationSettings | None = None) -> FastAPI:
    if settings is None:
        settings = ApplicationSettings.create_from_envs()
    assert settings  # nosec

    logging.basicConfig(level=settings.log_level)
    logging.root.setLevel(settings.log_level)
    config_all_loggers(
        log_format_local_dev_enabled=settings.API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.API_SERVER_LOG_FILTER_MAPPING,
    )
    _logger.debug("App settings:\n%s", settings.json(indent=2))

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

    setup_rabbitmq(app)

    if settings.API_SERVER_WEBSERVER:
        webserver.setup(app, settings.API_SERVER_WEBSERVER)
    if app.state.settings.API_SERVER_TRACING:
        setup_tracing(app, app.state.settings.API_SERVER_TRACING, APP_NAME)

    if settings.API_SERVER_CATALOG:
        catalog.setup(app, settings.API_SERVER_CATALOG)

    if settings.API_SERVER_STORAGE:
        storage.setup(app, settings.API_SERVER_STORAGE)

    if settings.API_SERVER_DIRECTOR_V2:
        director_v2.setup(app, settings.API_SERVER_DIRECTOR_V2)

    # setup app
    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))

    exceptions.setup_exception_handlers(
        app, is_debug=settings.SC_BOOT_MODE == BootModeEnum.DEBUG
    )

    if settings.API_SERVER_PROFILING:
        app.add_middleware(ProfilerMiddleware)

    if app.state.settings.API_SERVER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    # routing

    # healthcheck at / and at /VTAG/
    app.include_router(health_router)

    # api under /v*
    api_router = create_router(settings)
    app.include_router(api_router, prefix=f"/{API_VTAG}")

    # NOTE: cleanup all OpenAPIs https://github.com/ITISFoundation/osparc-simcore/issues/3487
    use_route_names_as_operation_ids(app)
    return app
