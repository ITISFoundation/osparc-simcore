from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db


def setup(app: FastAPI):
    async def on_startup() -> None:
        await connect_to_db(app, app.state.settings.RESOURCE_USAGE_TRACKER_POSTGRES)

    async def on_shutdown() -> None:
        await close_db_connection(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
