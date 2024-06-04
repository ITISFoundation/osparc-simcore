import logging
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from fastapi import FastAPI
from servicelib.db_async_engine import close_db_connection, connect_to_db

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..db.events import setup_default_product
from ..services.director import close_director, setup_director
from .background_tasks import start_registry_sync_task, stop_registry_sync_task

_logger = logging.getLogger(__name__)


EventCallable: TypeAlias = Callable[[], Awaitable[None]]


def create_on_startup(app: FastAPI) -> EventCallable:
    async def _() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

        # setup connection to pg db
        if app.state.settings.CATALOG_POSTGRES:
            await connect_to_db(app, app.state.settings.CATALOG_POSTGRES)
            await setup_default_product(app)

        if app.state.settings.CATALOG_DIRECTOR:
            # setup connection to director
            await setup_director(app)

            # FIXME: check director service is in place and ready. Hand-shake??
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1728
            await start_registry_sync_task(app)

        _logger.info("Application started")

    return _


def create_on_shutdown(app: FastAPI) -> EventCallable:
    async def _() -> None:
        _logger.info("Application stopping")

        if app.state.settings.CATALOG_DIRECTOR:
            try:
                await stop_registry_sync_task(app)
                await close_director(app)
                await close_db_connection(app)
            except Exception:  # pylint: disable=broad-except
                _logger.exception("Unexpected error while closing application")

        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    return _
