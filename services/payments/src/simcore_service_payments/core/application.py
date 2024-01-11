from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from simcore_service_payments.services.notifier import setup_notifier
from simcore_service_payments.services.socketio import setup_socketio

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.rest.routes import setup_rest_api
from ..api.rpc.routes import setup_rpc_api_routes
from ..services.auto_recharge_listener import setup_auto_recharge_listener
from ..services.payments_gateway import setup_payments_gateway
from ..services.postgres import setup_postgres
from ..services.rabbitmq import setup_rabbitmq
from ..services.resource_usage_tracker import setup_resource_usage_tracker
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

    # Listening to Rabbitmq
    setup_auto_recharge_listener(app)
    setup_socketio(app)
    setup_notifier(app)

    if app.state.settings.PAYMENTS_ADD_METRICS_ENDPOINT:
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
