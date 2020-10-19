import inspect
import logging
from typing import Callable

from fastapi import FastAPI

from ..meta import WELCOME_MSG
from ..services import director_v0, docker_registry, remote_debug
from ..services.remote_debug import setup_remote_debugging
from .settings import BootModeEnum

logger = logging.getLogger(__name__)


def remote_debug_on_start(app: FastAPI):
    setup_remote_debugging(
        force_enabled=app.state.settings.boot_mode == BootModeEnum.DEBUG
    )


submodules_events = [
    (
        remote_debug.__name__,
        remote_debug_on_start,
        lambda a: None,
    ),
    (docker_registry.__name__, docker_registry.on_stop, docker_registry.on_stop),
    (director_v0.__name__, director_v0.on_start, director_v0.on_stop),
]


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        for module_name, on_start, _ in submodules_events:
            logger.debug("Starting %s", module_name)
            if inspect.iscoroutinefunction(on_start):
                await on_start(app)
            else:
                on_start(app)
        # Started, welcome!
        print(WELCOME_MSG)

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def stop_app() -> None:
        for module_name, _, on_stop in submodules_events.reverse():
            try:
                logger.debug("Stopping %s", module_name)
                if inspect.iscoroutinefunction(on_stop):
                    await on_stop(app)
                else:
                    on_stop(app)
            except Exception:  # pylint: disable=broad-except
                logger.warning("Failed while stopping %s", module_name, exc_info=True)

    return stop_app
