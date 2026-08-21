import logging

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.postgres_lifespan import configure_postgres_database
from servicelib.fastapi.tracing import configure_fastapi_app_tracing
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.rest.routes import setup_api_routes
from ..api.rpc.routes import configure_rpc_api_routes
from ..exceptions.handlers import setup_exception_handlers
from ..services.background_task_periodic_heartbeat_check_setup import (
    configure_periodic_heartbeat_check,
)
from ..services.fire_and_forget_setup import configure_fire_and_forget
from ..services.modules.rabbitmq import configure_rabbitmq
from ..services.modules.redis import configure_redis
from ..services.modules.s3 import configure_s3
from ..services.process_message_running_service_setup import (
    configure_process_message_running_service,
)
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
) -> None:
    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(app, app_lifespan, tracing_config=tracing_config)

    configure_fire_and_forget(app_lifespan)

    if settings.RESOURCE_USAGE_TRACKER_POSTGRES:
        configure_postgres_database(
            app_lifespan,
            settings=settings.RESOURCE_USAGE_TRACKER_POSTGRES,
            tracing_config=tracing_config,
        )
    configure_redis(app_lifespan)
    configure_rabbitmq(app, app_lifespan)
    if settings.RESOURCE_USAGE_TRACKER_S3:
        configure_s3(app_lifespan)

    configure_rpc_api_routes(app_lifespan)
    configure_periodic_heartbeat_check(app_lifespan)
    configure_process_message_running_service(app_lifespan)


def create_app(
    settings: ApplicationSettings,
    tracing_config: TracingConfig,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=APP_STARTED_BANNER_MSG,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            debug=settings.RESOURCE_USAGE_TRACKER_DEBUG,
            title=f"{PROJECT_NAME} web API",
            description=SUMMARY,
            version=API_VERSION,
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            docs_url="/dev/doc",
            redoc_url=None,  # default disabled, see below
            lifespan=app_lifespan,
        )
        override_fastapi_openapi_method(app)

        # STATE
        app.state.settings = settings
        assert app.state.settings.API_VERSION == API_VERSION  # nosec

        _configure_plugins(app, app_lifespan, settings, tracing_config)

    setup_api_routes(app)
    setup_exception_handlers(app)

    return app
