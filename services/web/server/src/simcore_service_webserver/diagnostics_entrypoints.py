""" Handler functions and routing for diagnostics entrypoints

"""
import asyncio
import logging
from contextlib import suppress
from typing import List

from aiohttp import ClientError, ClientSession, web
from aiohttp.web import Request
from models_library.app_diagnostics import AppStatusCheck
from servicelib import openapi
from servicelib.client_session import get_client_session
from servicelib.utils import logged_gather

from . import __version__, catalog_client, db, director_v2, storage_api
from ._meta import api_version, app_name
from .diagnostics_core import HealthError, assert_healthy_app
from .utils import get_task_info, get_tracemalloc_info

log = logging.getLogger(__name__)


async def get_app_health(request: web.Request):
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


async def get_app_diagnostics(request: web.Request):
    """
    Usage
        /v0/status/diagnostics?top_tracemalloc=10 with display top 10 files allocating the most memory
    """
    # tasks in loop
    data = {"loop_tasks": [get_task_info(task) for task in asyncio.Task.all_tasks()]}

    # allocated memory
    if request.query.get("top_tracemalloc", False):
        top = int(request.query["top_tracemalloc"])
        data.update({"top_tracemalloc": get_tracemalloc_info(top)})

    return web.json_response(data)


async def get_app_status(request: Request):
    # TODO: add tester required

    SERVICES = ("postgres", "storage", "director_v2", "catalog")

    def _get_url_for(operation_id):
        return str(
            request.url.with_path(str(request.app.router[operation_id].url_for()))
        )

    def _get_client_session_info():

        # https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession
        client: ClientSession = get_client_session(request.app)
        info = {"instance": str(client)}

        if not client.closed:
            # https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.BaseConnector
            info.update(
                {
                    "limit": client.connector.limit,
                    "limit_per_host": client.connector.limit_per_host,
                }
            )

        return info

    check = AppStatusCheck.parse_obj(
        {
            "app_name": app_name,
            "version": api_version,
            "services": {name: {"healthy": False} for name in SERVICES},
            "sessions": {"main": _get_client_session_info()},
            #
            "url": _get_url_for("get_app_status"),
            "diagnostics_url": _get_url_for("get_app_diagnotics"),
        }
    )

    # concurrent checks of service states

    async def _check_pg():
        check.services["postgres"] = {
            "healthy": await db.is_service_responsive(request.app),
            "pool": db.get_engine_state(request.app),
        }

    async def _check_storage():
        is_healthy = await storage_api.is_healthy(request.app)
        status = None

        if is_healthy:
            with suppress(ClientError):
                status = await storage_api.get_app_status(request.app)

        check.services["storage"] = {"healthy": is_healthy, "status": status}

    async def _check_director2():
        check.services["director_v2"] = {
            "healthy": await director_v2.is_healthy(request.app)
        }

    async def _check_catalog():
        check.services["catalog"] = {
            "healthy": await catalog_client.is_service_responsive(request.app)
        }

    await logged_gather(
        _check_pg(),
        _check_storage(),
        _check_director2(),
        _check_catalog(),
        log=log,
        reraise=False,
    )

    return check.dict(exclude_unset=True)


def create_rest_routes(specs: openapi.Spec) -> List[web.RouteDef]:
    # NOTE: these are routes with paths starting with v0/*

    routes = []
    base_path: str = openapi.get_base_path(specs)

    path, handle = "/health", get_app_health
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(base_path + path, handle, name=operation_id))

    # NOTE: Internal. Not shown in api/docs
    path, handle = "/status/diagnostics", get_app_diagnostics
    operation_id = (
        "get_app_diagnotics"  # specs.paths[path].operations['get'].operation_id
    )
    routes.append(web.get(base_path + path, handle, name=operation_id))

    path, handle = "/status", get_app_status
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(base_path + path, handle, name=operation_id))

    return routes
