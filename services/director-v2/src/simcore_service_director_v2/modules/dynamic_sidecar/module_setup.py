from fastapi import FastAPI

from . import api_client, scheduler
from servicelib.fastapi import long_running_tasks


def setup(app: FastAPI) -> None:
    long_running_tasks.client.setup(app)

    async def on_startup() -> None:
        await api_client.setup(app)
        await scheduler.setup_scheduler(app)

    async def on_shutdown() -> None:
        await scheduler.shutdown_scheduler(app)
        await api_client.shutdown(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
