from fastapi import FastAPI
from servicelib.fastapi.db_asyncpg_engine import close_db_connection, connect_to_db

from ..._meta import APP_NAME


def setup(app: FastAPI):
    async def on_startup() -> None:
        await connect_to_db(app, app.state.settings.EFS_GUARDIAN_POSTGRES, application_name=APP_NAME)

    async def on_shutdown() -> None:
        await close_db_connection(app)

    app.router.on_startup.append(on_startup)
    app.router.on_shutdown.append(on_shutdown)


def get_database_engine(app: FastAPI):
    return app.state.engine
