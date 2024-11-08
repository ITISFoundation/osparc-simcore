""" Handler functions and routing for diagnostics

"""

import asyncio
import logging
from contextlib import suppress
from typing import Any

from aiohttp import ClientError, ClientSession, web
from models_library.app_diagnostics import AppStatusCheck
from pydantic import BaseModel, Field
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.utils import logged_gather

from .._meta import API_VERSION, APP_NAME, api_version_prefix
from ..catalog.client import is_catalog_service_responsive
from ..db import plugin
from ..director_v2 import api as director_v2_api
from ..login.decorators import login_required
from ..resource_usage._client import is_resource_usage_tracking_service_responsive
from ..security.decorators import permission_required
from ..storage import api as storage_api
from ..utils import TaskInfoDict, get_task_info, get_tracemalloc_info
from ..utils_aiohttp import envelope_json_response

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class StatusDiagnosticsQueryParam(BaseModel):
    top_tracemalloc: int | None = Field(default=None)


class StatusDiagnosticsGet(BaseModel):
    loop_tasks: list[TaskInfoDict]
    top_tracemalloc: list[str]


@routes.get(f"/{api_version_prefix}/status/diagnostics", name="get_app_diagnostics")
@login_required
@permission_required("diagnostics.read")
async def get_app_diagnostics(request: web.Request):
    """
    Usage
        /v0/status/diagnostics?top_tracemalloc=10 with display top 10 files allocating the most memory
    """
    # tasks in loop
    data: dict[str, Any] = {
        "loop_tasks": [get_task_info(task) for task in asyncio.all_tasks()]
    }

    # allocated memory
    query_params: StatusDiagnosticsQueryParam = parse_request_query_parameters_as(
        StatusDiagnosticsQueryParam, request
    )
    if query_params.top_tracemalloc is not None:
        data.update(
            top_tracemalloc=get_tracemalloc_info(top=query_params.top_tracemalloc)
        )

    assert StatusDiagnosticsGet.model_validate(data) is not None  # nosec
    return envelope_json_response(data)


@routes.get(f"/{api_version_prefix}/status", name="get_app_status")
@login_required
@permission_required("diagnostics.read")
async def get_app_status(request: web.Request):
    SERVICES = (
        "postgres",
        "storage",
        "director_v2",
        "catalog",
        "resource_usage_tracker",
    )

    def _get_url_for(operation_id, **kwargs):
        return str(
            request.url.with_path(
                str(request.app.router[operation_id].url_for(**kwargs))
            )
        )

    def _get_client_session_info():
        client: ClientSession = get_client_session(request.app)
        info: dict[str, Any] = {"instance": str(client)}

        if not client.closed and client.connector:
            info.update(
                {
                    "limit": client.connector.limit,
                    "limit_per_host": client.connector.limit_per_host,
                }
            )

        return info

    check = AppStatusCheck.model_validate(
        {
            "app_name": APP_NAME,
            "version": API_VERSION,
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
            "healthy": await plugin.is_service_responsive(request.app),
            "pool": plugin.get_engine_state(request.app),
        }

    async def _check_storage():
        check.services["storage"] = {
            "healthy": await storage_api.is_healthy(request.app),
            "status_url": _get_url_for("get_service_status", service_name="storage"),
        }

    async def _check_director2():
        check.services["director_v2"] = {
            "healthy": await director_v2_api.is_healthy(request.app)
        }

    async def _check_catalog():
        check.services["catalog"] = {
            "healthy": await is_catalog_service_responsive(request.app)
        }

    async def _check_resource_usage_tracker():
        check.services["resource_usage_tracker"] = {
            "healthy": await is_resource_usage_tracking_service_responsive(request.app)
        }

    await logged_gather(
        _check_pg(),
        _check_storage(),
        _check_director2(),
        _check_catalog(),
        _check_resource_usage_tracker(),
        log=_logger,
        reraise=False,
    )

    return envelope_json_response(check.model_dump(exclude_unset=True))


@routes.get(f"/{api_version_prefix}/status/{{service_name}}", name="get_service_status")
@login_required
@permission_required("diagnostics.read")
async def get_service_status(request: web.Request):
    service_name = request.match_info["service_name"]

    if service_name == "storage":
        with suppress(ClientError):
            status = await storage_api.get_app_status(request.app)
            return envelope_json_response(status)

    raise web.HTTPNotFound
