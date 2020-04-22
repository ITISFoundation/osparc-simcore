import logging
import sys
from pathlib import Path

from fastapi import FastAPI

from . import application, endpoints_auth, endpoints_check, endpoints_user
from .__version__ import api_vtag
from .db import setup_db
from .utils.remote_debug import setup_remote_debugging
from .settings import AppSettings

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

log = logging.getLogger(__name__)


def build_app() -> FastAPI:
    """
        Creates a sets up app
    """
    app_settings = AppSettings()

    logging.root.setLevel(app_settings.loglevel)

    app: FastAPI = application.create(settings=app_settings)

    @app.on_event("startup")
    def startup_event():  # pylint: disable=unused-variable
        log.info("Application started")
        setup_remote_debugging()

    # ROUTES
    app.include_router(endpoints_check.router)

    app.include_router(endpoints_auth.router, tags=["auth"], prefix=f"/{api_vtag}")
    app.include_router(endpoints_user.router, tags=["users"], prefix=f"/{api_vtag}")

    # SUBMODULES setups
    setup_db(app)
    # NOTE: add new here!
    #  ...

    @app.on_event("shutdown")
    def shutdown_event():  # pylint: disable=unused-variable
        log.info("Application shutdown")

    return app


# SINGLETON FastAPI app
the_app: FastAPI = build_app()
