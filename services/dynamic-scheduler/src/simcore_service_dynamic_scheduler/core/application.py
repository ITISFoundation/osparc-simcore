from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from servicelib.fastapi.profiler_middleware import ProfilerMiddleware
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
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
from ..api.frontend import setup_frontend
from ..api.rest.routes import setup_rest_api
from ..api.rpc.routes import setup_rpc_api_routes
from ..services.catalog import setup_catalog
from ..services.deferred_manager import setup_deferred_manager
from ..services.director_v0 import setup_director_v0
from ..services.director_v2 import setup_director_v2
from ..services.notifier import setup_notifier
from ..services.rabbitmq import setup_rabbitmq
from ..services.redis import setup_redis
from ..services.service_tracker import setup_service_tracker
from ..services.status_monitor import setup_status_monitor
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
        redoc_url=None,  # default disabled, see below
    )
    override_fastapi_openapi_method(app)

    # STATE
    app.state.settings = app_settings
    assert app.state.settings.API_VERSION == API_VERSION  # nosec

    if app.state.settings.DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        setup_prometheus_instrumentation(app)

    if app.state.settings.DYNAMIC_SCHEDULER_PROFILING:
        app.add_middleware(ProfilerMiddleware)
    if app.state.settings.DYNAMIC_SCHEDULER_TRACING:
        setup_tracing(
            app,
            app.state.settings.DYNAMIC_SCHEDULER_TRACING,
            APP_NAME,
        )

    # PLUGINS SETUP

    setup_director_v2(app)
    setup_director_v0(app)
    setup_catalog(app)

    setup_rabbitmq(app)
    setup_rpc_api_routes(app)

    setup_redis(app)

    setup_notifier(app)

    setup_service_tracker(app)
    setup_deferred_manager(app)
    setup_status_monitor(app)

    setup_rest_api(app)
    setup_frontend(app)

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
