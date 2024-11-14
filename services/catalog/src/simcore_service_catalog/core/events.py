import logging
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db
from servicelib.logging_utils import log_context
from settings_library.tracing import TracingSettings

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..db.events import setup_default_product
from ..services.director import close_director, setup_director
from .background_tasks import start_registry_sync_task, stop_registry_sync_task

_logger = logging.getLogger(__name__)


EventCallable: TypeAlias = Callable[[], Awaitable[None]]


def _flush_started_banner() -> None:
    # WARNING: this function is spied in the tests
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201


def _flush_finished_banner() -> None:
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


def create_on_startup(
    app: FastAPI, tracing_settings: TracingSettings | None
) -> EventCallable:
    async def _() -> None:
        _flush_started_banner()

        # setup connection to pg db
        if app.state.settings.CATALOG_POSTGRES:
            await connect_to_db(app, app.state.settings.CATALOG_POSTGRES)
            await setup_default_product(app)

        if app.state.settings.CATALOG_DIRECTOR:
            # setup connection to director
            await setup_director(app, tracing_settings=tracing_settings)

            # FIXME: check director service is in place and ready. Hand-shake??
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1728
            await start_registry_sync_task(app)

        _logger.info("Application started")

    return _


def create_on_shutdown(app: FastAPI) -> EventCallable:
    async def _() -> None:

        with log_context(_logger, logging.INFO, "Application shutdown"):
            if app.state.settings.CATALOG_DIRECTOR:
                try:
                    await stop_registry_sync_task(app)
                    await close_director(app)
                    await close_db_connection(app)
                except Exception:  # pylint: disable=broad-except
                    _logger.exception("Unexpected error while closing application")

            _flush_finished_banner()

    return _
