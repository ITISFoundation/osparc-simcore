import logging
import sys
from pathlib import Path

from fastapi import FastAPI

from __version__ import api_version_prefix

from . import application, endpoints_auth, endpoints_check, endpoints_user
from .db import setup_db
from .utils.remote_debug import setup_remote_debugging

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

log = logging.getLogger(__name__)


def setup():
    app: FastAPI = application.create()

    @app.on_event("startup")
    def startup_event():  # pylint: disable=unused-variable
        log.info("Application started")
        setup_remote_debugging()


    # ROUTES
    app.include_router(endpoints_check.router, tags=["check"])

    app.include_router(
        endpoints_auth.router, tags=["auth"], prefix=f"/{api_version_prefix}"
    )
    app.include_router(
        endpoints_user.router, tags=["users"], prefix=f"/{api_version_prefix}"
    )

    # SUBMODULES setups
    setup_db(app)


    @app.on_event("shutdown")
    def shutdown_event():  # pylint: disable=unused-variable
        log.info("Application shutdown")

    return app



# SINGLETON FastAPI app
the_app = setup()
