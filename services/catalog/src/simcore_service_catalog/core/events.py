import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanStateKeys,
    postgres_lifespan,
)

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from ..db.events import setup_database
from ..services.director import setup_director
from ..services.function_services import setup_function_services
from ..services.rabbitmq import setup_rabbitmq
from .background_tasks import setup_background_task
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def flush_started_banner() -> None:
    # WARNING: this function is spied in the tests
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201


def flush_finished_banner() -> None:
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


async def _setup_app(app: FastAPI) -> AsyncIterator[State]:
    flush_started_banner()

    settings: ApplicationSettings = app.state.settings

    yield {
        PostgresLifespanStateKeys.POSTGRES_SETTINGS: settings.CATALOG_POSTGRES,
    }

    flush_finished_banner()


def create_app_lifespan():
    # app lifespan
    app_lifespan = LifespanManager()
    app_lifespan.add(_setup_app)

    # - postgres lifespan
    postgres_lifespan.add(setup_database)
    app_lifespan.include(postgres_lifespan)

    # - rabbitmq lifespan
    app_lifespan.add(setup_rabbitmq)

    # - director lifespan
    app_lifespan.add(setup_director)

    # - function services lifespan
    app_lifespan.add(setup_function_services)

    # - background task lifespan
    app_lifespan.add(setup_background_task)

    return app_lifespan
