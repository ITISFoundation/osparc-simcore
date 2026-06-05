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
from .lifespan_utils import LifespanOnStartupError, PublisherLifespan, lifespan_context

_logger = logging.getLogger(__name__)


class PostgresLifespanState(StrEnum):
    POSTGRES_SETTINGS = "postgres_settings"
    POSTGRES_ASYNC_ENGINE = "postgres.async_engine"


class PostgresConfigurationError(LifespanOnStartupError):
    msg_template = (
        "Invalid postgres settings [={settings}] on startup. Note that postgres cannot be disabled using settings"
    )


def create_postgres_database_input_state(settings: PostgresSettings) -> State:
    return {PostgresLifespanState.POSTGRES_SETTINGS: settings}


def _create_postgres_database_lifespan(settings: PostgresSettings) -> PublisherLifespan:
    async def _lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}.{_lifespan.__name__}"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            if settings is None or not isinstance(settings, PostgresSettings):
                raise PostgresConfigurationError(settings=settings)

            assert isinstance(settings, PostgresSettings)  # nosec

            async_engine: AsyncEngine = await create_async_engine_and_database_ready(settings, app.title)

            try:
                yield {
                    PostgresLifespanState.POSTGRES_ASYNC_ENGINE: async_engine,
                    **called_state,
                }

            finally:
                with log_catch(_logger, reraise=False):
                    await asyncio.wait_for(async_engine.dispose(), timeout=10)

    return _lifespan


def _create_postgres_default_publisher_lifespan(
    state_key: PostgresLifespanState = PostgresLifespanState.POSTGRES_ASYNC_ENGINE,
    app_state_attr: str = "engine",
) -> PublisherLifespan:
    async def _publisher_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}.{_publisher_lifespan.__name__}"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            async_engine = state.get(state_key)
            if not isinstance(async_engine, AsyncEngine):
                msg = f"Postgres async engine not found in lifespan state under key '{state_key}'"
                raise TypeError(msg)

            setattr(app.state, app_state_attr, async_engine)
            yield called_state

    return _publisher_lifespan


def _create_postgres_lifespan_manager(
    settings: PostgresSettings,
    publisher_lifespan: PublisherLifespan | None = None,
) -> LifespanManager[FastAPI]:
    postgres_lifespan_manager = LifespanManager()
    postgres_lifespan_manager.add(_create_postgres_database_lifespan(settings=settings))
    postgres_lifespan_manager.add(publisher_lifespan or _create_postgres_default_publisher_lifespan())
    return postgres_lifespan_manager


def configure_postgres_database(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: PostgresSettings,
    publisher_lifespan: PublisherLifespan | None = None,
) -> None:
    app_lifespan.include(
        _create_postgres_lifespan_manager(
            settings=settings,
            publisher_lifespan=publisher_lifespan,
        )
    )


async def postgres_database_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
    """Backward-compatible postgres lifespan that expects settings in input state."""
    _lifespan_name = f"{__name__}.{postgres_database_lifespan.__name__}"

    with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
        # Validate input state
        settings = state[PostgresLifespanState.POSTGRES_SETTINGS]

        if settings is None or not isinstance(settings, PostgresSettings):
            raise PostgresConfigurationError(settings=settings)

        assert isinstance(settings, PostgresSettings)  # nosec

        # connect to database
        async_engine: AsyncEngine = await create_async_engine_and_database_ready(settings, app.title)

        try:
            yield {
                PostgresLifespanState.POSTGRES_ASYNC_ENGINE: async_engine,
                **called_state,
            }

        finally:
            with log_catch(_logger, reraise=False):
                await asyncio.wait_for(async_engine.dispose(), timeout=10)
