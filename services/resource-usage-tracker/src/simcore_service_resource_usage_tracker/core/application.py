import logging

from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import setup_tracing

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
from ..services.modules.db import setup as setup_db
from ..services.modules.rabbitmq import setup as setup_rabbitmq
from ..services.modules.redis import setup as setup_redis
from ..services.modules.s3 import setup as setup_s3
from ..services.process_message_running_service_setup import (
    setup as setup_process_message_running_service,
)
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> FastAPI:
    _logger.info("app settings: %s", settings.model_dump_json(indent=1))

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
    setup_api_routes(app)

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

    if app.state.settings.RESOURCE_USAGE_TRACKER_TRACING:
        setup_tracing(
            app,
            app.state.settings.RESOURCE_USAGE_TRACKER_TRACING,
            app.state.settings.APP_NAME,
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
