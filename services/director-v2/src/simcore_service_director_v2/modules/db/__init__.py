from fastapi import FastAPI
from servicelib.db_asyncpg_pool_metrics import setup_pool_metrics_instrumentation
from servicelib.fastapi.db_asyncpg_engine import (
    close_db_connection,
    connect_to_db,
)
from servicelib.fastapi.db_asyncpg_engine import get_engine as get_db_engine
from servicelib.tracing import TracingConfig
from settings_library.postgres import PostgresSettings

from ..._meta import APP_NAME


def setup(
    app: FastAPI,
    settings: PostgresSettings,
    *,
    tracing_config: TracingConfig | None,
    monitoring_enabled: bool,
) -> None:
    async def on_startup() -> None:
        await connect_to_db(app, settings=settings, application_name=APP_NAME, tracing_config=tracing_config)
        if monitoring_enabled:
            setup_pool_metrics_instrumentation(
                get_db_engine(app),
                app.state.instrumentation.db_pool_metrics,
            )

    async def on_shutdown() -> None:
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


__all__: tuple[str, ...] = (
    "get_db_engine",
    "setup",
)
