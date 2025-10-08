import logging

from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import (
    initialize_fastapi_app_tracing,
    setup_tracing,
)
from servicelib.tracing import TracingConfig

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.rest.routes import setup_api_routes
from ..api.rpc.routes import setup_rpc_api_routes
from ..exceptions.handlers import setup_exception_handlers
from ..services.background_task_periodic_heartbeat_check_setup import (
    setup as setup_background_task_periodic_heartbeat_check,
)
from ..services.fire_and_forget_setup import setup as fire_and_forget_setup
from ..services.modules.db import setup as setup_db
from ..services.modules.rabbitmq import setup as setup_rabbitmq
from ..services.modules.redis import setup as setup_redis
from ..services.modules.s3 import setup as setup_s3
from ..services.process_message_running_service_setup import (
    setup as setup_process_message_running_service,
)
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings, tracing_config: TracingConfig) -> FastAPI:
    app = FastAPI(
        debug=settings.RESOURCE_USAGE_TRACKER_DEBUG,
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled, see below
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    # PLUGINS SETUP
    if tracing_config.tracing_enabled:
        setup_tracing(
            app,
            tracing_config,
        )
    setup_api_routes(app)
    fire_and_forget_setup(app)

    if settings.RESOURCE_USAGE_TRACKER_POSTGRES:
        setup_db(app)
    setup_redis(app)
    setup_rabbitmq(app)
    if settings.RESOURCE_USAGE_TRACKER_S3:
        # Needed for CSV export functionality
        setup_s3(app)

    setup_rpc_api_routes(app)  # Requires Rabbit, S3
    setup_background_task_periodic_heartbeat_check(app)  # Requires Redis, DB

    setup_process_message_running_service(app)  # Requires Rabbit

    if tracing_config.tracing_enabled:
        initialize_fastapi_app_tracing(
            app,
            tracing_config=tracing_config,
        )

    # ERROR HANDLERS
    setup_exception_handlers(app)

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
