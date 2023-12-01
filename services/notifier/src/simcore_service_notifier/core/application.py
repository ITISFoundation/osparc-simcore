from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from simcore_service_notifier.services.socketio import setup_socketio

from .._meta import (
    API_VERSION,
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
    PROJECT_NAME,
    SUMMARY,
)
from ..services.postgres import setup_postgres
from ..services.rabbitmq import setup_rabbitmq
from .settings import ApplicationSettings


def create_app(settings: ApplicationSettings | None = None) -> FastAPI:

    app_settings = settings or ApplicationSettings.create_from_envs()

    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url="/doc",
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

    # Listening to Rabbitmq
    setup_socketio(app)

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
