from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from models_library.basic_types import BootModeEnum
from servicelib.fastapi import timing_middleware
from starlette.middleware.base import BaseHTTPMiddleware

from ._services import set_services_caching_enabled
from .errors import setup_rest_api_error_handlers
from .routes import setup_rest_api_routes


def configure_rest_api(app: FastAPI) -> None:
    settings = app.state.settings

    # toggle the REST-layer services caches from settings (e.g. for testing/debugging)
    set_services_caching_enabled(enabled=settings.CATALOG_DIRECTOR_SERVICES_CACHE_ENABLED)

    if settings.SC_BOOT_MODE != BootModeEnum.PRODUCTION:
        # middleware to time requests (ONLY for development)
        app.add_middleware(BaseHTTPMiddleware, dispatch=timing_middleware.add_process_time_header)

    app.add_middleware(GZipMiddleware)

    setup_rest_api_routes(app)
    setup_rest_api_error_handlers(app)
