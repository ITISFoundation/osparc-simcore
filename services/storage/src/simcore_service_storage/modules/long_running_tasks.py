from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks._server import setup

from .._meta import API_VTAG


def setup_rest_api_long_running_tasks(app: FastAPI) -> None:
    setup(
        app,
        router_prefix=f"/{API_VTAG}/futures",
    )
