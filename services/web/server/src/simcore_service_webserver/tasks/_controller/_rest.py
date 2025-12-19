import logging
from typing import Final

from aiohttp import web
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.long_running_tasks.server import (
    get_long_running_manager,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.rest_responses import (
    create_data_response,
)
from servicelib.celery.models import OwnerMetadata
from servicelib.long_running_tasks import lrt_api

from ..._meta import API_VTAG
from ...celery import get_task_manager
from ...login.decorators import login_required
from ...long_running_tasks.plugin import webserver_request_context_decorator
from ...models import AuthenticatedRequestContext, WebServerOwnerMetadata
from .. import _tasks_service
from ._rest_exceptions import handle_rest_requests_exceptions
from ._rest_schemas import TaskPathParams, TaskStreamQueryParams, TaskStreamResponse

log = logging.getLogger(__name__)


routes = web.RouteTableDef()

_task_prefix: Final[str] = f"/{API_VTAG}/tasks"


@routes.get(
    _task_prefix,
    name="get_async_jobs",
)
@login_required
@handle_rest_requests_exceptions
@webserver_request_context_decorator
async def get_async_jobs(request: web.Request) -> web.Response:
    inprocess_long_running_manager = get_long_running_manager(request.app)
    inprocess_tracked_tasks = await lrt_api.list_tasks(
        inprocess_long_running_manager.rpc_client,
        inprocess_long_running_manager.lrt_namespace,
        inprocess_long_running_manager.get_task_context(request),
    )

    _req_ctx = AuthenticatedRequestContext.model_validate(request)

    tasks = await _tasks_service.list_tasks(
        get_task_manager(request.app),
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=_req_ctx.user_id,
                product_name=_req_ctx.product_name,
            ).model_dump()
        ),
    )

    return create_data_response(
        [
            TaskGet(
                task_id=f"{task.job_id}",
                task_name=task.job_name,
                status_href=f"{request.url.with_path(str(request.app.router['get_async_job_status'].url_for(task_id=str(task.job_id))))}",
                abort_href=f"{request.url.with_path(str(request.app.router['cancel_async_job'].url_for(task_id=str(task.job_id))))}",
                result_href=f"{request.url.with_path(str(request.app.router['get_async_job_result'].url_for(task_id=str(task.job_id))))}",
            )
            for task in tasks
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


@routes.get(
    _task_prefix + "/{task_id}",
    name="get_async_job_status",
)
@login_required
@handle_rest_requests_exceptions
async def get_async_job_status(request: web.Request) -> web.Response:
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    _path_params = parse_request_path_parameters_as(TaskPathParams, request)

    task_status = await _tasks_service.get_task_status(
        get_task_manager(request.app),
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=_req_ctx.user_id,
                product_name=_req_ctx.product_name,
            ).model_dump()
        ),
        task_uuid=_path_params.task_id,
    )

    _task_id = f"{task_status.job_id}"
    return create_data_response(
        TaskStatus(
            task_progress=TaskProgress(
                task_id=_task_id, percent=task_status.progress.percent_value
            ),
            done=task_status.done,
            started=None,
        ),
        status=status.HTTP_200_OK,
    )


@routes.delete(
    _task_prefix + "/{task_id}",
    name="cancel_async_job",
)
@login_required
@handle_rest_requests_exceptions
async def cancel_async_job(request: web.Request) -> web.Response:
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    _path_params = parse_request_path_parameters_as(TaskPathParams, request)

    await _tasks_service.cancel_task(
        get_task_manager(request.app),
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=_req_ctx.user_id,
                product_name=_req_ctx.product_name,
            ).model_dump()
        ),
        task_uuid=_path_params.task_id,
    )

    return web.Response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    _task_prefix + "/{task_id}/result",
    name="get_async_job_result",
)
@login_required
@handle_rest_requests_exceptions
async def get_async_job_result(request: web.Request) -> web.Response:
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    _path_params = parse_request_path_parameters_as(TaskPathParams, request)

    task_result = await _tasks_service.get_task_result(
        get_task_manager(request.app),
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=_req_ctx.user_id,
                product_name=_req_ctx.product_name,
            ).model_dump()
        ),
        task_uuid=_path_params.task_id,
    )

    return create_data_response(
        TaskResult(result=task_result.result, error=None),
        status=status.HTTP_200_OK,
    )


@routes.get(
    _task_prefix + "/{task_id}/stream",
    name="get_async_job_stream",
)
@login_required
@handle_rest_requests_exceptions
async def get_async_job_stream(request: web.Request) -> web.Response:
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    _path_params = parse_request_path_parameters_as(TaskPathParams, request)
    _query_params: TaskStreamQueryParams = parse_request_query_parameters_as(
        TaskStreamQueryParams, request
    )

    task_result, end = await _tasks_service.pull_task_stream_items(
        get_task_manager(request.app),
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=_req_ctx.user_id,
                product_name=_req_ctx.product_name,
            ).model_dump()
        ),
        task_uuid=_path_params.task_id,
        limit=_query_params.limit,
    )

    return create_data_response(
        TaskStreamResponse(items=[r.data for r in task_result], end=end),
        status=status.HTTP_200_OK,
    )
