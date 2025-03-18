"""Handlers exposed by storage subsystem

Mostly resolves and redirect to storage API
"""

import logging
from typing import Final
from uuid import UUID

from aiohttp import web
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobId,
    AsyncJobNameData,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.generics import Envelope
from pydantic import BaseModel
from servicelib.aiohttp import status
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.rest_responses import create_data_response
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import (
    abort,
    get_result,
    get_status,
    list_jobs,
)

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..models import RequestContext
from ..rabbitmq import get_rabbitmq_rpc_client
from ..security.decorators import permission_required
from ._exception_handlers import handle_data_export_exceptions

log = logging.getLogger(__name__)


routes = web.RouteTableDef()

_task_prefix: Final[str] = f"/{API_VTAG}/tasks"


@routes.get(
    _task_prefix,
    name="get_async_jobs",
)
@login_required
@permission_required("storage.files.*")
@handle_data_export_exceptions
async def get_async_jobs(request: web.Request) -> web.Response:
    session = get_client_session(request.app)
    async with session.request(
        "GET",
        request.url.with_path(str(request.app.router["list_tasks"].url_for())),
        cookies=request.cookies,
    ) as resp:
        if resp.status != status.HTTP_200_OK:
            return web.Response(
                status=resp.status,
                body=await resp.read(),
                content_type=resp.content_type,
            )
        inprocess_tasks = (
            Envelope[list[TaskGet]].model_validate_json(await resp.text()).data
        )
        assert inprocess_tasks is not None  # nosec

    _req_ctx = RequestContext.model_validate(request)

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)

    user_async_jobs = await list_jobs(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id_data=AsyncJobNameData(
            user_id=_req_ctx.user_id, product_name=_req_ctx.product_name
        ),
        filter_="",
    )
    return create_data_response(
        [
            TaskGet(
                task_id=f"{job.job_id}",
                task_name=f"{job.job_id}",
                status_href=f"{request.url.with_path(str(request.app.router['get_async_job_status'].url_for(task_id=str(job.job_id))))}",
                abort_href=f"{request.url.with_path(str(request.app.router['abort_async_job'].url_for(task_id=str(job.job_id))))}",
                result_href=f"{request.url.with_path(str(request.app.router['get_async_job_result'].url_for(task_id=str(job.job_id))))}",
            )
            for job in user_async_jobs
        ]
        + inprocess_tasks,
        status=status.HTTP_200_OK,
    )


class _StorageAsyncJobId(BaseModel):
    task_id: AsyncJobId


@routes.get(
    _task_prefix + "/{task_id}/status",
    name="get_async_job_status",
)
@login_required
@handle_data_export_exceptions
async def get_async_job_status(request: web.Request) -> web.Response:

    _req_ctx = RequestContext.model_validate(request)
    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)

    async_job_get = parse_request_path_parameters_as(_StorageAsyncJobId, request)
    async_job_rpc_status = await get_status(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=async_job_get.task_id,
        job_id_data=AsyncJobNameData(
            user_id=_req_ctx.user_id, product_name=_req_ctx.product_name
        ),
    )
    _task_id = f"{async_job_rpc_status.job_id}"
    return create_data_response(
        TaskStatus(
            task_progress=TaskProgress(
                task_id=_task_id, percent=async_job_rpc_status.progress.actual_value
            ),
            done=async_job_rpc_status.done,
            started=None,
        ),
        status=status.HTTP_200_OK,
    )


@routes.delete(
    _task_prefix + "/{task_id}",
    name="abort_async_job",
)
@login_required
@permission_required("storage.files.*")
@handle_data_export_exceptions
async def abort_async_job(request: web.Request) -> web.Response:

    _req_ctx = RequestContext.model_validate(request)

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)
    async_job_get = parse_request_path_parameters_as(_StorageAsyncJobId, request)
    await abort(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=async_job_get.task_id,
        job_id_data=AsyncJobNameData(
            user_id=_req_ctx.user_id, product_name=_req_ctx.product_name
        ),
    )
    return web.Response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    _task_prefix + "/{task_id}/result",
    name="get_async_job_result",
)
@login_required
@permission_required("storage.files.*")
@handle_data_export_exceptions
async def get_async_job_result(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        task_id: UUID

    _req_ctx = RequestContext.model_validate(request)

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)
    async_job_get = parse_request_path_parameters_as(_PathParams, request)
    async_job_rpc_result = await get_result(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=async_job_get.task_id,
        job_id_data=AsyncJobNameData(
            user_id=_req_ctx.user_id, product_name=_req_ctx.product_name
        ),
    )

    return create_data_response(
        TaskResult(result=async_job_rpc_result.result, error=None),
        status=status.HTTP_200_OK,
    )
