from fastapi import FastAPI
from servicelib.fastapi import long_running_tasks
from servicelib.long_running_tasks.task import RedisNamespace

from ...core.settings import AppSettings
from . import api_client, scheduler

_LONG_RUNNING_TASKS_NAMESPACE: RedisNamespace = "director-v2"


def setup(app: FastAPI) -> None:
    settings: AppSettings = app.state.settings

    long_running_tasks.client.setup(app)
    long_running_tasks.server.setup(
        app,
        redis_settings=settings.REDIS,
        redis_namespace=_LONG_RUNNING_TASKS_NAMESPACE,
    )

    async def on_startup() -> None:
        await api_client.setup(app)
        await scheduler.setup_scheduler(app)

    async def on_shutdown() -> None:
        await scheduler.shutdown_scheduler(app)
        await api_client.shutdown(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
