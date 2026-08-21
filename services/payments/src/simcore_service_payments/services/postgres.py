from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.postgres_lifespan import (
    configure_postgres_database as _configure_postgres_database,
)
from servicelib.tracing import TracingConfig
from settings_library.postgres import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine


def configure_postgres(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: PostgresSettings,
    tracing_config: TracingConfig | None,
) -> None:
    _configure_postgres_database(
        app_lifespan,
        settings=settings,
        tracing_config=tracing_config,
    )


def get_async_engine(app: FastAPI) -> AsyncEngine:
    assert app.state.engine  # nosec
    engine: AsyncEngine = app.state.engine
    return engine
