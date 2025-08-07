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
    AsyncJobFilter,
    AsyncJobId,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from pydantic import BaseModel
from servicelib.aiohttp import status
from servicelib.aiohttp.long_running_tasks.server import (
    get_long_running_manager,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.rest_responses import create_data_response
from servicelib.long_running_tasks import lrt_api
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs

from .._meta import API_VTAG
from ..constants import ASYNC_JOB_CLIENT_NAME
from ..login.decorators import login_required
from ..long_running_tasks import webserver_request_context_decorator
from ..models import AuthenticatedRequestContext
from ..rabbitmq import get_rabbitmq_rpc_client
from ..security.decorators import permission_required
from ._exception_handlers import handle_export_data_exceptions

log = logging.getLogger(__name__)


routes = web.RouteTableDef()

_task_prefix: Final[str] = f"/{API_VTAG}/tasks"


@routes.get(
    _task_prefix,
    name="get_async_jobs",
)
@login_required
@permission_required("storage.files.*")
@handle_export_data_exceptions
@webserver_request_context_decorator
async def get_async_jobs(request: web.Request) -> web.Response:
    inprocess_long_running_manager = get_long_running_manager(request.app)
    inprocess_tracked_tasks = await lrt_api.list_tasks(
        inprocess_long_running_manager,
        inprocess_long_running_manager.get_task_context(request),
    )

    _req_ctx = AuthenticatedRequestContext.model_validate(request)

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)

    user_async_jobs = await async_jobs.list_jobs(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_filter=AsyncJobFilter(
            user_id=_req_ctx.user_id,
            product_name=_req_ctx.product_name,
            client_name=ASYNC_JOB_CLIENT_NAME,
        ),
        filter_="",
    )
    return create_data_response(
        [
            TaskGet(
                task_id=f"{job.job_id}",
                task_name=job.job_name,
                status_href=f"{request.url.with_path(str(request.app.router['get_async_job_status'].url_for(task_id=str(job.job_id))))}",
                abort_href=f"{request.url.with_path(str(request.app.router['cancel_async_job'].url_for(task_id=str(job.job_id))))}",
                result_href=f"{request.url.with_path(str(request.app.router['get_async_job_result'].url_for(task_id=str(job.job_id))))}",
            )
            for job in user_async_jobs
        ]
        + [
            TaskGet(
                task_id=f"{task.task_id}",
                status_href=f"{request.app.router['get_task_status'].url_for(task_id=task.task_id)}",
                abort_href=f"{request.app.router['remove_task'].url_for(task_id=task.task_id)}",
                result_href=f"{request.app.router['get_task_result'].url_for(task_id=task.task_id)}",
            )
            for task in inprocess_tracked_tasks
        ],
        status=status.HTTP_200_OK,
    )


class _StorageAsyncJobId(BaseModel):
    task_id: AsyncJobId


@routes.get(
    _task_prefix + "/{task_id}",
    name="get_async_job_status",
)
@login_required
@handle_export_data_exceptions
async def get_async_job_status(request: web.Request) -> web.Response:

    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)

    async_job_get = parse_request_path_parameters_as(_StorageAsyncJobId, request)
    async_job_rpc_status = await async_jobs.status(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=async_job_get.task_id,
        job_filter=AsyncJobFilter(
            user_id=_req_ctx.user_id,
            product_name=_req_ctx.product_name,
            client_name=ASYNC_JOB_CLIENT_NAME,
        ),
    )
    _task_id = f"{async_job_rpc_status.job_id}"
    return create_data_response(
        TaskStatus(
            task_progress=TaskProgress(
                task_id=_task_id, percent=async_job_rpc_status.progress.percent_value
            ),
            done=async_job_rpc_status.done,
            started=None,
        ),
        status=status.HTTP_200_OK,
    )


@routes.delete(
    _task_prefix + "/{task_id}",
    name="cancel_async_job",
)
@login_required
@permission_required("storage.files.*")
@handle_export_data_exceptions
async def cancel_async_job(request: web.Request) -> web.Response:

    _req_ctx = AuthenticatedRequestContext.model_validate(request)

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)
    async_job_get = parse_request_path_parameters_as(_StorageAsyncJobId, request)

    await async_jobs.cancel(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=async_job_get.task_id,
        job_filter=AsyncJobFilter(
            user_id=_req_ctx.user_id,
            product_name=_req_ctx.product_name,
            client_name=ASYNC_JOB_CLIENT_NAME,
        ),
    )

    return web.Response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    _task_prefix + "/{task_id}/result",
    name="get_async_job_result",
)
@login_required
@permission_required("storage.files.*")
@handle_export_data_exceptions
async def get_async_job_result(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        task_id: UUID

    _req_ctx = AuthenticatedRequestContext.model_validate(request)

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)
    async_job_get = parse_request_path_parameters_as(_PathParams, request)
    async_job_rpc_result = await async_jobs.result(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        job_id=async_job_get.task_id,
        job_filter=AsyncJobFilter(
            user_id=_req_ctx.user_id,
            product_name=_req_ctx.product_name,
            client_name=ASYNC_JOB_CLIENT_NAME,
        ),
    )

    return create_data_response(
        TaskResult(result=async_job_rpc_result.result, error=None),
        status=status.HTTP_200_OK,
    )
