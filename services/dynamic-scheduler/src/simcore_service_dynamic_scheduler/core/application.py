from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler import initialize_profiler
from servicelib.fastapi.prometheus_instrumentation import (
    initialize_prometheus_instrumentation,
)
from servicelib.fastapi.tracing import initialize_tracing

from .._meta import API_VERSION, API_VTAG, APP_NAME, PROJECT_NAME, SUMMARY
from ..api.frontend import initialize_frontend
from ..api.rest.routes import initialize_rest_api
from . import events
from .settings import ApplicationSettings


def create_app(settings: ApplicationSettings | None = None) -> FastAPI:
    app_settings = settings or ApplicationSettings.create_from_envs()

    app = FastAPI(
        title=f"{PROJECT_NAME} web API",
        description=SUMMARY,
        version=API_VERSION,
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        docs_url=(
            "/doc" if app_settings.DYNAMIC_SCHEDULER_SWAGGER_API_DOC_ENABLED else None
        ),
        redoc_url=None,
        lifespan=events.create_app_lifespan(),
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = app_settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    initialize_rest_api(app)

    if app_settings.DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        initialize_prometheus_instrumentation(app)

    initialize_frontend(app)

    if app_settings.DYNAMIC_SCHEDULER_TRACING:
        initialize_tracing(app, app_settings.DYNAMIC_SCHEDULER_TRACING, APP_NAME)

    if app_settings.DYNAMIC_SCHEDULER_PROFILING:
        initialize_profiler(app)

    return app
