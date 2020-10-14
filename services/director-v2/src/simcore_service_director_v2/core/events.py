import logging
from typing import Callable

from fastapi import FastAPI

from ..meta import WELCOME_MSG
from ..services.remote_debug import setup_remote_debugging
from ..services.docker_registry import setup_docker_registry, shutdown_docker_registry
from .settings import BootModeEnum

logger = logging.getLogger(__name__)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:

        # setup connection to remote debugger (if applies)
        setup_remote_debugging(
            force_enabled=app.state.settings.boot_mode == BootModeEnum.DEBUG
        )

        setup_docker_registry(app)

        print(WELCOME_MSG)

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def stop_app() -> None:
        try:
            logger.info("Application stopping %s", app)
            shutdown_docker_registry(app)

        except Exception:  # pylint: disable=broad-except
            logger.exception("Stopping application")

    return stop_app
