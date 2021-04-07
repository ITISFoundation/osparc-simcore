""" Handler functions and routing for diagnostics

"""
import asyncio
import logging
from contextlib import suppress

from aiohttp import ClientError, ClientSession, web
from models_library.app_diagnostics import AppStatusCheck
from servicelib.client_session import get_client_session
from servicelib.utils import logged_gather

from . import catalog_client, db, director_v2, storage_api
from ._meta import __version__, api_version, api_version_prefix, app_name
from .diagnostics_core import HealthError, assert_healthy_app
from .login.decorators import login_required
from .security_decorators import permission_required
from .utils import get_task_info, get_tracemalloc_info

log = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get(f"/{api_version_prefix}/health", name="check_health")
async def get_app_health(request: web.Request):
    # diagnostics of incidents
    try:
        assert_healthy_app(request.app)
    except HealthError as err:
        log.error("Unhealthy application: %s", err)
        raise web.HTTPServiceUnavailable()

    data = {
        "name": app_name,
        "version": __version__,
        "api_version": api_version,
    }
    return data


@routes.get(f"/{api_version_prefix}/status/diagnostics", name="get_app_diagnostics")
@login_required
@permission_required("diagnostics.read")
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

    return data


@routes.get(f"/{api_version_prefix}/status", name="get_app_status")
@login_required
@permission_required("diagnostics.read")
async def get_app_status(request: web.Request):
    SERVICES = ("postgres", "storage", "director_v2", "catalog")

    def _get_url_for(operation_id, **kwargs):
        return str(
            request.url.with_path(
                str(request.app.router[operation_id].url_for(**kwargs))
            )
        )

    def _get_client_session_info():
        client: ClientSession = get_client_session(request.app)
        info = {"instance": str(client)}

        if not client.closed:
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
            # hyperlinks
            "url": _get_url_for("get_app_status"),
            "diagnostics_url": _get_url_for("get_app_diagnostics"),
        }
    )

    # concurrent checks of service states

    async def _check_pg():
        check.services["postgres"] = {
            "healthy": await db.is_service_responsive(request.app),
            "pool": db.get_engine_state(request.app),
        }

    async def _check_storage():
        check.services["storage"] = {
            "healthy": await storage_api.is_healthy(request.app),
            "status_url": _get_url_for("get_service_status", service_name="storage"),
        }

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


@routes.get(f"/{api_version_prefix}/status/{{service_name}}", name="get_service_status")
@login_required
@permission_required("diagnostics.read")
async def get_service_status(request: web.Request):
    service_name = request.match_info["service_name"]

    if service_name == "storage":
        with suppress(ClientError):
            return await storage_api.get_app_status(request.app)

    raise web.HTTPNotFound()
