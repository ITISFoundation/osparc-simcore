from fastapi import FastAPI
from servicelib.db_asyncpg_utils import check_postgres_liveness, with_async_pg_engine
from settings_library.postgres import PostgresSettings

from ..core.settings import ApplicationSettings
from .service_liveness import (
    wait_for_service_liveness,
)


async def wait_for_database_liveness(app: FastAPI) -> None:
    """
    Checks if the postgres engine is alive and can be used.
    """

    app_settings = app.state.settings
    assert isinstance(app_settings, ApplicationSettings)  # nosec
    postgres_settings = app_settings.POSTGRES_SETTINGS
    assert isinstance(postgres_settings, PostgresSettings)  # nosec
    async with with_async_pg_engine(postgres_settings) as engine:
        await wait_for_service_liveness(
            check_postgres_liveness,
            engine,
            service_name="Postgres",
            endpoint=postgres_settings.dsn,
        )
