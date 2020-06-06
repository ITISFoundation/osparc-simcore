import logging
import sys
from pathlib import Path

from fastapi import FastAPI

from .core import application
from .core.config import AppSettings
from .__version__ import api_vtag
from .api.routes.openapi import router as api_router
from .core.events import create_start_app_handler, create_stop_app_handler


current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

log = logging.getLogger(__name__)


def init_application() -> FastAPI:
    """
        Creates a sets up app
    """
    config = AppSettings()
    logging.root.setLevel(config.loglevel)

    app: FastAPI = application.create(settings=config)

    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))

    # app.add_exception_handler(HTTPException, http_error_handler)
    # app.add_exception_handler(RequestValidationError, http422_error_handler)

    app.include_router(api_router, prefix=f"/{api_vtag}")

    return app


# SINGLETON FastAPI app
the_app: FastAPI = init_application()
