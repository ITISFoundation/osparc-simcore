from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.long_running_tasks import client as long_running_tasks_client
from servicelib.fastapi.long_running_tasks import server as long_running_tasks_server

from ..._meta import APP_NAME
from ...core.settings import AppSettings
from . import api_client, scheduler


async def _api_client_lifespan(app: FastAPI) -> AsyncIterator[None]:
    await api_client.setup(app)
    try:
        yield
    finally:
        await api_client.shutdown(app)


async def _scheduler_lifespan(app: FastAPI) -> AsyncIterator[None]:
    await scheduler.setup_scheduler(app)
    try:
        yield
    finally:
        await scheduler.shutdown_scheduler(app)


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

    # NOTE: registered as two separate lifespans so that, if the scheduler fails to start,
    # the LifespanManager still tears down the already-started api_client (and vice versa).
    app_lifespan.add(_api_client_lifespan)
    app_lifespan.add(_scheduler_lifespan)
