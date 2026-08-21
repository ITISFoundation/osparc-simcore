from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.long_running_tasks import client as long_running_tasks_client
from servicelib.fastapi.long_running_tasks import server as long_running_tasks_server

from ..._meta import APP_NAME
from ...core.settings import AppSettings
from . import api_client, scheduler


def configure_dynamic_sidecar(app: FastAPI, app_lifespan: LifespanManager) -> None:
    settings: AppSettings = app.state.settings

    long_running_tasks_client.configure_client(app_lifespan)
    long_running_tasks_server.configure_server(
        app,
        app_lifespan,
        redis_settings=settings.REDIS,
        rabbit_settings=settings.DIRECTOR_V2_RABBITMQ,
        lrt_namespace=APP_NAME,
    )

    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        await api_client.setup(app)
        await scheduler.setup_scheduler(app)
        try:
            yield
        finally:
            await scheduler.shutdown_scheduler(app)
            await api_client.shutdown(app)

    app_lifespan.add(_lifespan)
