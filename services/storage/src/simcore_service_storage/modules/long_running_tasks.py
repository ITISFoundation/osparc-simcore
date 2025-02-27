import asyncio

from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks._server import setup

from .._meta import API_VTAG


def setup_rest_api_long_running_tasks_for_uploads(app: FastAPI) -> None:
    setup(
        app,
        router_prefix=f"/{API_VTAG}/futures",
    )

    app.state.completed_upload_tasks = {}


def get_completed_upload_tasks(app: FastAPI) -> dict[str, asyncio.Task]:
    assert isinstance(app.state.completed_upload_tasks, dict)  # nosec
    return app.state.completed_upload_tasks
