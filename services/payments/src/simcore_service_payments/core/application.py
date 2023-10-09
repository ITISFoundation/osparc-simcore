from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..api.rest.routes import setup_rest_api_routes
from ..api.rpc.routes import setup_rpc_api_routes
from ..services.payments_gateway import setup_payments_gateway
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

    # APIs w/ webserver
    setup_rabbitmq(app)
    setup_rpc_api_routes(app)

    # APIs w/ payments-gateway
    setup_payments_gateway(app)
    setup_rest_api_routes(app)

    # APIs w/ RUT
    setup_resource_usage_tracker(app)

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
