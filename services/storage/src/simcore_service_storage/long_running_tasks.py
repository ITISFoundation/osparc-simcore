from aiohttp import web
from servicelib.aiohttp.long_running_tasks.server import setup

from ._meta import API_VTAG


def setup_rest_api_long_running_tasks(app: web.Application) -> None:
    setup(
        app,
        router_prefix=f"/{API_VTAG}/futures",
    )
