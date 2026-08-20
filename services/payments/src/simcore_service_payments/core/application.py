import logging

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.lifespan_utils import Lifespan, configure_app_lifespan
from servicelib.fastapi.monitoring import configure_prometheus_instrumentation
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import configure_fastapi_app_tracing
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
from ..api.rest.routes import setup_rest_api
from ..api.rpc.routes import configure_rpc_api_routes
from ..services.auto_recharge_listener import configure_auto_recharge_listener
from ..services.notifier import configure_notifier
from ..services.payments_gateway import setup_payments_gateway
from ..services.postgres import configure_postgres
from ..services.rabbitmq import configure_rabbitmq
from ..services.resource_usage_tracker import setup_resource_usage_tracker
from ..services.socketio import configure_socketio
from ..services.stripe import setup_stripe
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def _configure_plugins(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    app_tracing_config: TracingConfig,
) -> None:
    if app_tracing_config.tracing_enabled:
        configure_fastapi_app_tracing(
            app,
            app_lifespan,
            tracing_config=app_tracing_config,
        )

    configure_postgres(app_lifespan, tracing_config=app_tracing_config)

    configure_rabbitmq(app_lifespan)
    configure_rpc_api_routes(app_lifespan)

    setup_payments_gateway(app)
    setup_rest_api(app)

    setup_resource_usage_tracker(app)

    setup_stripe(app)

    configure_auto_recharge_listener(app_lifespan)
    configure_socketio(app_lifespan)
    configure_notifier(app_lifespan)

    if app.state.settings.PAYMENTS_PROMETHEUS_INSTRUMENTATION_ENABLED:
        configure_prometheus_instrumentation(app, app_lifespan)


def create_app(
    settings: ApplicationSettings | None = None,
    tracing_config: TracingConfig | None = None,
    logging_lifespan: Lifespan | None = None,
) -> FastAPI:
    app_settings = settings or ApplicationSettings.create_from_envs()
    if not settings:
        _logger.info(
            "Application settings: %s",
            json_dumps(app_settings, indent=2, sort_keys=True),
        )
    app_tracing_config = tracing_config or TracingConfig.create(
        service_name=APP_NAME, tracing_settings=app_settings.PAYMENTS_TRACING
    )
    with configure_app_lifespan(
        logging_lifespan=logging_lifespan,
        starting_banner=APP_STARTING_BANNER_MSG,
        started_banner=APP_STARTED_BANNER_MSG,
        shutdown_complete_banner=APP_FINISHED_BANNER_MSG,
    ) as app_lifespan:
        app = FastAPI(
            title=f"{PROJECT_NAME} web API",
            description=SUMMARY,
            version=API_VERSION,
            openapi_url=f"/api/{API_VTAG}/openapi.json",
            docs_url="/doc" if app_settings.PAYMENTS_SWAGGER_API_DOC_ENABLED else None,
            redoc_url=None,  # default disabled, see below
            lifespan=app_lifespan,
        )
        override_fastapi_openapi_method(app)

        # STATE
        app.state.settings = app_settings
        app.state.tracing_config = app_tracing_config
        assert app.state.settings.API_VERSION == API_VERSION  # nosec

        _configure_plugins(app, app_lifespan, app_tracing_config)

    return app
