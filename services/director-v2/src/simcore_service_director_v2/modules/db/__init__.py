from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.db_asyncpg_pool_metrics import setup_pool_metrics_instrumentation
from servicelib.fastapi.db_asyncpg_engine import get_engine as get_db_engine
from servicelib.fastapi.postgres_lifespan import configure_postgres_database
from servicelib.tracing import TracingConfig
from settings_library.postgres import PostgresSettings


async def _pool_metrics_lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_pool_metrics_instrumentation(get_db_engine(app), app.state.instrumentation.db_pool_metrics)
    yield


def configure_db(
    app_lifespan: LifespanManager,
    *,
    settings: PostgresSettings,
    tracing_config: TracingConfig | None,
    monitoring_enabled: bool,
) -> None:
    configure_postgres_database(app_lifespan, settings=settings, tracing_config=tracing_config)
    if monitoring_enabled:
        app_lifespan.add(_pool_metrics_lifespan)


__all__: tuple[str, ...] = (
    "configure_db",
    "get_db_engine",
)
