import asyncio
import logging
from collections.abc import AsyncIterator
from enum import StrEnum

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from settings_library.postgres import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db_asyncpg_utils import create_async_engine_and_database_ready
from ..logging_utils import log_catch
from .lifespan_utils import LifespanOnStartupError, PublisherLifespan, create_publisher_lifespan, lifespan_context
from .tracing import get_tracing_config

_logger = logging.getLogger(__name__)


class PostgresLifespanState(StrEnum):
    POSTGRES_ASYNC_ENGINE = "postgres.async_engine"


class PostgresConfigurationError(LifespanOnStartupError):
    msg_template = (
        "Invalid postgres settings [={settings}] on startup. Note that postgres cannot be disabled using settings"
    )


def _create_postgres_database_lifespan(settings: PostgresSettings) -> PublisherLifespan:
    async def _lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}.{_lifespan.__name__}"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            if settings is None or not isinstance(settings, PostgresSettings):
                raise PostgresConfigurationError(settings=settings)

            assert isinstance(settings, PostgresSettings)  # nosec

            async_engine: AsyncEngine = await create_async_engine_and_database_ready(
                settings,
                app.title,
                tracing_config=get_tracing_config(app),
            )

            try:
                yield {
                    PostgresLifespanState.POSTGRES_ASYNC_ENGINE: async_engine,
                    **called_state,
                }

            finally:
                with log_catch(_logger, reraise=False):
                    await asyncio.wait_for(async_engine.dispose(), timeout=10)

    return _lifespan


def _create_postgres_lifespan_manager(
    settings: PostgresSettings,
) -> LifespanManager[FastAPI]:
    postgres_lifespan_manager = LifespanManager()
    postgres_lifespan_manager.add(_create_postgres_database_lifespan(settings=settings))
    postgres_lifespan_manager.add(
        create_publisher_lifespan(
            state_key=PostgresLifespanState.POSTGRES_ASYNC_ENGINE,
            app_state_attr="engine",
        )
    )
    return postgres_lifespan_manager


def configure_postgres_database(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: PostgresSettings,
) -> None:
    app_lifespan.include(_create_postgres_lifespan_manager(settings=settings))
