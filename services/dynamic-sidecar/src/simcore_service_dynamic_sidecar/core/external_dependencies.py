from fastapi import FastAPI
from servicelib.utils import logged_gather

from .postgres import wait_for_postgres_liveness
from .rabbitmq import wait_for_rabbitmq_liveness
from .storage import wait_for_storage_liveness


def setup_check_dependencies(app: FastAPI) -> None:
    async def on_startup() -> None:
        await logged_gather(
            *[
                wait_for_storage_liveness(app),
                wait_for_rabbitmq_liveness(app),
                wait_for_postgres_liveness(app),
            ],
            reraise=True,
        )

    app.add_event_handler("startup", on_startup)
