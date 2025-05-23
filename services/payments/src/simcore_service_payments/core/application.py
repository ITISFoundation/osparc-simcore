from fastapi import FastAPI
from servicelib.fastapi.monitoring import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.tracing import setup_tracing

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.rest.routes import setup_rest_api
from ..api.rpc.routes import setup_rpc_api_routes
from ..services.auto_recharge_listener import setup_auto_recharge_listener
from ..services.notifier import setup_notifier
from ..services.payments_gateway import setup_payments_gateway
from ..services.postgres import setup_postgres
from ..services.rabbitmq import setup_rabbitmq
from ..services.resource_usage_tracker import setup_resource_usage_tracker
from ..services.socketio import setup_socketio
from ..services.stripe import setup_stripe
from .settings import ApplicationSettings


def create_app(settings: ApplicationSettings | None = None) -> FastAPI:

    app_settings = settings or ApplicationSettings.create_from_envs()

    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/doc" if app_settings.PAYMENTS_SWAGGER_API_DOC_ENABLED else None,
        redoc_url=None,  # default disabled, see below
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = app_settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    # PLUGINS SETUP
    if app.state.settings.PAYMENTS_TRACING:
        setup_tracing(app, app.state.settings.PAYMENTS_TRACING, APP_NAME)

    # API w/ postgres db
    setup_postgres(app)

    # APIs w/ webserver
    setup_rabbitmq(app)
    setup_rpc_api_routes(app)

    # APIs w/ payments-gateway
    setup_payments_gateway(app)
    setup_rest_api(app)

    # APIs w/ RUT
    setup_resource_usage_tracker(app)

    # APIs w/ Stripe
    setup_stripe(app)

    # Listening to Rabbitmq
    setup_auto_recharge_listener(app)
    setup_socketio(app)
    setup_notifier(app)

    if app.state.settings.PAYMENTS_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    # ERROR HANDLERS
    # ... add here ...

    # EVENTS
    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
