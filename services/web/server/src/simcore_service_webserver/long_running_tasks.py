from functools import wraps
from typing import Any

from aiohttp import web
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, Field
from servicelib.aiohttp.long_running_tasks._server import (
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)
from servicelib.aiohttp.long_running_tasks.server import (
    TaskGet,
    TaskProtocol,
    create_task_name_from_request,
    get_tasks_manager,
    setup,
    start_task,
)
from servicelib.aiohttp.typing_extension import Handler

from ._constants import RQ_PRODUCT_KEY
from ._meta import API_VTAG
from .login.decorators import RQT_USERID_KEY, login_required


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)


def start_task_with_context(
    request: web.Request, task: TaskProtocol, **task_kwargs: Any
) -> TaskGet:
    req_ctx = _RequestContext.parse_obj(request)
    task_manager = get_tasks_manager(request.app)
    task_name = create_task_name_from_request(request)
    task_id = start_task(
        task_manager,
        task,
        task_context=jsonable_encoder(req_ctx),
        task_name=task_name,
        **task_kwargs,
    )
    status_url = request.app.router["get_task_status"].url_for(task_id=task_id)
    result_url = request.app.router["get_task_result"].url_for(task_id=task_id)
    abort_url = request.app.router["cancel_and_delete_task"].url_for(task_id=task_id)
    return TaskGet(
        task_id=task_id,
        task_name=task_name,
        status_href=f"{status_url}",
        result_href=f"{result_url}",
        abort_href=f"{abort_url}",
    )


def _webserver_request_context_decorator(handler: Handler):
    @wraps(handler)
    async def _test_task_context_decorator(
        request: web.Request,
    ) -> web.StreamResponse:
        """this task context callback tries to get the user_id from the query if available"""
        req_ctx = _RequestContext.parse_obj(request)
        request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY] = jsonable_encoder(req_ctx)
        return await handler(request)

    return _test_task_context_decorator


def setup_long_running_tasks(app: web.Application) -> None:
    setup(
        app,
        router_prefix=f"/{API_VTAG}/tasks",
        handler_check_decorator=login_required,
        task_request_context_decorator=_webserver_request_context_decorator,
    )
