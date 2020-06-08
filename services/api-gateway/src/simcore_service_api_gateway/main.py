import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from loguru import logger

from .__version__ import api_vtag
from .api.routes.openapi import router as api_router
from .core import application
from .core.config import AppSettings
from .core.events import create_start_app_handler, create_stop_app_handler

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def init_application() -> FastAPI:
    """
        Creates a sets up app
    """
    config = AppSettings()
    logger.add(sys.stderr, level=config.loglevel)

    app: FastAPI = application.create(settings=config)

    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))

    # app.add_exception_handler(HTTPException, http_error_handler)
    # app.add_exception_handler(RequestValidationError, http422_error_handler)

    app.include_router(api_router, prefix=f"/{api_vtag}")

    use_route_names_as_operation_ids(app)
    return app


def use_route_names_as_operation_ids(app: FastAPI) -> None:
    """
    Simplify operation IDs so that generated API clients have simpler function
    names.

    Should be called only after all routes have been added.

    PROS: auto-generated client has one-to-one correspondence and human readable names
    CONS: highly coupled. Changes in server handler names will change client
    """
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name




# SINGLETON FastAPI app
the_app: FastAPI = init_application()
