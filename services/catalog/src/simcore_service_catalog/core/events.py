import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeAlias

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanStateKeys,
    postgres_lifespan,
)
from servicelib.logging_utils import log_context

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..db.events import setup_database
from ..services.director import close_director, setup_director
from .background_tasks import start_registry_sync_task, stop_registry_sync_task
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


EventCallable: TypeAlias = Callable[[], Awaitable[None]]


def flush_started_banner() -> None:
    # WARNING: this function is spied in the tests
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201


def flush_finished_banner() -> None:
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _main_setup(app: FastAPI) -> AsyncIterator[State]:
    flush_started_banner()

    settings: ApplicationSettings = app.state.settings

    yield {
        PostgresLifespanStateKeys.POSTGRES_SETTINGS: settings.CATALOG_POSTGRES,
    }

    flush_finished_banner()


def _create_on_startup(app: FastAPI) -> EventCallable:
    async def _() -> None:

        if app.state.settings.CATALOG_DIRECTOR:
            # setup connection to director
            await setup_director(app)

            # FIXME: check director service is in place and ready. Hand-shake??
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1728
            await start_registry_sync_task(app)

        _logger.info("Application started")

    return _


def _create_on_shutdown(app: FastAPI) -> EventCallable:
    async def _() -> None:

        with log_context(_logger, logging.INFO, "Application shutdown"):
            if app.state.settings.CATALOG_DIRECTOR:
                try:
                    await stop_registry_sync_task(app)
                    await close_director(app)
                except Exception:  # pylint: disable=broad-except
                    _logger.exception("Unexpected error while closing application")

    return _


@contextlib.asynccontextmanager
async def _other_setup(app: FastAPI) -> AsyncIterator[State]:

    await _create_on_startup(app)()

    yield {}

    await _create_on_shutdown(app)()


def create_app_lifespan():
    # app lifespan
    app_lifespan = LifespanManager()
    app_lifespan.add(_main_setup)

    # - postgres lifespan
    postgres_lifespan.add(setup_database)
    app_lifespan.include(postgres_lifespan)

    app_lifespan.add(_other_setup)

    return app_lifespan
