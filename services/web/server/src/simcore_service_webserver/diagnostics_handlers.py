import asyncio
import logging

from aiohttp import web

from . import __version__
from .diagnostics import DiagnosticError, assert_healthy_app
from .utils import get_task_info, get_tracemalloc_info

log = logging.getLogger(__name__)


async def check_health(request: web.Request):

    # diagnostics of incidents
    try:
        assert_healthy_app(request.app)
    except DiagnosticError as err:
        msg = f"Unhealthy service: {err}"
        log.error(msg)
        raise web.HTTPServiceUnavailable(reason=msg)

    data = {
        "name": __name__.split(".")[0],
        "version": str(__version__),
        "status": "SERVICE_RUNNING",
        "api_version": str(__version__),
    }
    return data


async def get_diagnostics(request: web.Request):
    """
        Usage
            /v0/diagnostics?top_tracemalloc=10 with display top 10 files allocating the most memory
    """
    # tasks in loop
    data = {"loop_tasks": [get_task_info(task) for task in asyncio.Task.all_tasks()]}

    # allocated memory
    if request.query.get("top_tracemalloc", False):
        top = int(request.query["top_tracemalloc"])
        data.update({"top_tracemalloc": get_tracemalloc_info(top)})

    return web.json_response(data)
