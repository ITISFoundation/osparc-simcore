""" Handler functions and routing for diagnostics entrypoints

"""
import asyncio
import logging
from typing import List

from aiohttp import web

from servicelib import openapi

from . import __version__
from .diagnostics_core import HealthError, assert_healthy_app
from .utils import get_task_info, get_tracemalloc_info

log = logging.getLogger(__name__)


async def check_health(request: web.Request):
    # diagnostics of incidents
    try:
        assert_healthy_app(request.app)
    except HealthError as err:
        log.error("Unhealthy application: %s", err)
        raise web.HTTPServiceUnavailable()

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


def create_rest_routes(specs: openapi.Spec) -> List[web.RouteDef]:
    # NOTE: these are routes with paths starting with v0/*

    routes = []
    base_path: str = openapi.get_base_path(specs)

    path, handle = "/health", check_health
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(base_path + path, handle, name=operation_id))

    # NOTE: Internal. Not shown in api/docs
    path, handle = "/diagnostics", get_diagnostics
    operation_id = "get_diagnotics"  # specs.paths[path].operations['get'].operation_id
    routes.append(web.get(base_path + path, handle, name=operation_id))

    return routes
