"""Handlers exposed by storage subsystem

Mostly resolves and redirect to storage API
"""

import logging
from typing import Final
from uuid import UUID

from aiohttp import web
from common_library.json_serialization import json_dumps
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from pydantic import BaseModel
from servicelib.aiohttp import status
from servicelib.aiohttp.long_running_tasks.server import (
    get_long_running_manager,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_headers_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.rest_responses import (
    create_data_response,
    create_event_stream_response,
)
from servicelib.celery.models import OwnerMetadata, TaskEventType
from servicelib.long_running_tasks import lrt_api
from servicelib.sse.models import SSEEvent, SSEHeaders

from .._meta import API_VTAG
from ..celery import get_task_manager
from ..login.decorators import login_required
from ..long_running_tasks.plugin import webserver_request_context_decorator
from ..models import AuthenticatedRequestContext, WebServerOwnerMetadata
from . import _service
from ._exception_handlers import handle_exceptions

log = logging.getLogger(__name__)


routes = web.RouteTableDef()

_task_prefix: Final[str] = f"/{API_VTAG}/tasks"


class _PathParams(BaseModel):
    task_id: UUID


@routes.get(
    _task_prefix,
    name="get_async_jobs",
)
@login_required
@handle_exceptions
@webserver_request_context_decorator
async def get_async_jobs(request: web.Request) -> web.Response:
    inprocess_long_running_manager = get_long_running_manager(request.app)
    inprocess_tracked_tasks = await lrt_api.list_tasks(
        inprocess_long_running_manager.rpc_client,
        inprocess_long_running_manager.lrt_namespace,
        inprocess_long_running_manager.get_task_context(request),
    )

    _req_ctx = AuthenticatedRequestContext.model_validate(request)

    tasks = await _service.list_tasks(
        task_manager=get_task_manager(request.app),
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
@handle_exceptions
async def get_async_job_status(request: web.Request) -> web.Response:
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_PathParams, request)

    task_manager = get_task_manager(request.app)
    task_status = await _service.get_task_status(
        task_manager=task_manager,
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=_req_ctx.user_id,
                product_name=_req_ctx.product_name,
            ).model_dump()
        ),
        task_uuid=path_params.task_id,
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
@handle_exceptions
async def cancel_async_job(request: web.Request) -> web.Response:
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_PathParams, request)

    task_manager = get_task_manager(request.app)
    await _service.cancel_task(
        task_manager=task_manager,
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=_req_ctx.user_id,
                product_name=_req_ctx.product_name,
            ).model_dump(),
        ),
        task_uuid=path_params.task_id,
    )

    return web.Response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    _task_prefix + "/{task_id}/result",
    name="get_async_job_result",
)
@login_required
@handle_exceptions
async def get_async_job_result(request: web.Request) -> web.Response:
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_PathParams, request)

    task_manager = get_task_manager(request.app)
    task_result = await _service.get_task_result(
        task_manager=task_manager,
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=_req_ctx.user_id,
                product_name=_req_ctx.product_name,
            ).model_dump()
        ),
        task_uuid=path_params.task_id,
    )

    return create_data_response(
        TaskResult(result=task_result, error=None),
        status=status.HTTP_200_OK,
    )


@routes.get(
    _task_prefix + "/{task_id}/stream",
    name="get_async_job_stream",
)
@login_required
@handle_exceptions
async def get_async_job_stream(request: web.Request) -> web.Response:
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_PathParams, request)
    header_params = parse_request_headers_as(SSEHeaders, request)

    async def event_generator():
        async for event_id, event in get_task_manager(request.app).consume_task_events(
            owner_metadata=OwnerMetadata.model_validate(
                WebServerOwnerMetadata(
                    user_id=_req_ctx.user_id,
                    product_name=_req_ctx.product_name,
                ).model_dump()
            ),
            task_uuid=path_params.task_id,
            last_id=header_params.last_event_id,
        ):
            yield SSEEvent(
                id=event_id, event=event.type, data=[json_dumps(event.data)]
            ).serialize()

            if event.type == TaskEventType.STATUS and event.is_done():
                break

    return create_event_stream_response(event_generator=event_generator)
