import logging

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.health import HealthCheckError, health_check_error_handler
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.tracing import configure_fastapi_app_tracing
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    APP_STARTED_DISABLED_BANNER_MSG,
    APP_STARTING_BANNER_MSG,
)
from ..api.rest.routes import setup_api_routes
from ..api.rpc.routes import configure_rpc_routes
from ..services.background_tasks_setup import configure_background_tasks
from ..services.efs_manager_setup import configure_efs_manager
from ..services.fire_and_forget_setup import configure_fire_and_forget
from ..services.modules.db import configure_db
from ..services.modules.rabbitmq import configure_rabbitmq
from ..services.modules.redis import configure_redis
from ..services.process_messages_setup import configure_process_messages
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    tracing_config: TracingConfig,
) -> None:
    if tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(app, app_lifespan, tracing_config=tracing_config)

    configure_rabbitmq(app, app_lifespan)
    configure_redis(app_lifespan)
    configure_db(app_lifespan, tracing_config=tracing_config)

    configure_rpc_routes(app_lifespan)
    configure_efs_manager(app_lifespan)
    configure_background_tasks(app_lifespan)
    configure_process_messages(app_lifespan)
    configure_fire_and_forget(app_lifespan)


def create_app(
    settings: ApplicationSettings | None = None,
    tracing_config: TracingConfig | None = None,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    app_settings = settings or ApplicationSettings.create_from_envs()
    tracing_config = tracing_config or TracingConfig.create(
        service_name=app_settings.APP_NAME,
        tracing_settings=app_settings.EFS_GUARDIAN_TRACING,
    )

    started_banner = APP_STARTED_BANNER_MSG
    if app_settings.EFS_GUARDIAN_AWS_EFS_SETTINGS is None:
        started_banner += APP_STARTED_DISABLED_BANNER_MSG

    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=started_banner,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            debug=app_settings.EFS_GUARDIAN_DEBUG,
            title=APP_NAME,
            description="Service to monitor and manage elastic file system",
            version=API_VERSION,
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            docs_url="/dev/doc",
            redoc_url=None,  # default disabled
            lifespan=app_lifespan,
        )
        # STATE
        app.state.settings = app_settings
        app.state.tracing_config = tracing_config
        assert app.state.settings.API_VERSION == API_VERSION  # nosec

        _configure_plugins(app, app_lifespan, tracing_config)

    setup_api_routes(app)
    app.add_exception_handler(HealthCheckError, health_check_error_handler)

    return app
