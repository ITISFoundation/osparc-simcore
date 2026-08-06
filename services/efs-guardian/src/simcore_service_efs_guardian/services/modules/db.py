from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db
from servicelib.tracing import TracingConfig

from ..._meta import APP_NAME


def setup(app: FastAPI, tracing_config: TracingConfig | None) -> None:
    async def on_startup() -> None:
        await connect_to_db(
            app,
            settings=app.state.settings.EFS_GUARDIAN_POSTGRES,
            application_name=APP_NAME,
            tracing_config=tracing_config,
        )

    async def on_shutdown() -> None:
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_database_engine(app: FastAPI):
    return app.state.engine
