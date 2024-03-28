from fastapi import FastAPI
from servicelib.common_aiopg_utils import is_postgres_responsive_async
from settings_library.postgres import PostgresSettings

from ..modules.service_liveness import wait_for_service_liveness
from .settings import ApplicationSettings


async def wait_for_postgres_liveness(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings
    postgres_settings: PostgresSettings = app_settings.POSTGRES_SETTINGS

    await wait_for_service_liveness(
        is_postgres_responsive_async,
        service_name="Postgres",
        endpoint=postgres_settings.dsn,
        dsn=postgres_settings.dsn,
    )
