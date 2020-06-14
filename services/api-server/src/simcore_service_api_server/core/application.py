import sys
from typing import Optional

from fastapi import FastAPI
from loguru import logger

from ..__version__ import api_version, api_vtag
from ..api.routes.openapi import router as api_router
from .events import create_start_app_handler, create_stop_app_handler
from .openapi import override_openapi_method, use_route_names_as_operation_ids
from .redoc import create_redoc_handler
from .settings import AppSettings


def init_app(settings: Optional[AppSettings] = None) -> FastAPI:
    """  Creates a customized app

    """
    if settings is None:
        settings = AppSettings()

    logger.add(sys.stderr, level=settings.loglevel)

    app = FastAPI(
        debug=settings.debug,
        title="Public API Server",
        description="osparc-simcore Public RESTful API Specifications",
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/devdocs",
        redoc_url=None,  # disabled
    )

    logger.debug(settings)
    app.state.settings = settings

    # overrides generation of openapi specs
    override_openapi_method(app)

    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))

    # app.add_exception_handler(HTTPException, http_error_handler)
    # app.add_exception_handler(RequestValidationError, http422_error_handler)

    redoc_html = create_redoc_handler(app)
    app.add_route("/docs", redoc_html, include_in_schema=False)

    app.include_router(api_router, prefix=f"/{api_vtag}")

    use_route_names_as_operation_ids(app)

    return app
