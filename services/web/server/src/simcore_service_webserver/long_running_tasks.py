from functools import wraps

from aiohttp import web
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import Field
from servicelib.aiohttp.long_running_tasks._constants import (
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)
from servicelib.aiohttp.long_running_tasks.server import setup
from servicelib.aiohttp.requests_validation import RequestParams
from servicelib.aiohttp.typing_extension import Handler
from servicelib.request_keys import RQT_USERID_KEY

from ._constants import RQ_PRODUCT_KEY
from ._meta import API_VTAG
from .login.decorators import login_required


class _RequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


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
