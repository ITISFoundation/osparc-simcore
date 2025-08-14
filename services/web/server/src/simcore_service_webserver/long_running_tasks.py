import logging
from functools import wraps
from typing import Final

from aiohttp import web
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.aiohttp.application_setup import ensure_single_setup
from servicelib.aiohttp.long_running_tasks._constants import (
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)
from servicelib.aiohttp.long_running_tasks.server import setup
from servicelib.aiohttp.typing_extension import Handler

from . import rabbitmq_settings, redis
from ._meta import API_VTAG
from .login.decorators import login_required
from .models import AuthenticatedRequestContext
from .projects.plugin import register_projects_long_running_tasks

_logger = logging.getLogger(__name__)


_LRT_NAMESPACE_PREFIX: Final[str] = "webserver-legacy"


def _get_namespace(suffix: str) -> str:
    return f"{_LRT_NAMESPACE_PREFIX}-{suffix}"


def webserver_request_context_decorator(handler: Handler):
    @wraps(handler)
    async def _test_task_context_decorator(
        request: web.Request,
    ) -> web.StreamResponse:
        """this task context callback tries to get the user_id from the query if available"""
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY] = jsonable_encoder(req_ctx)
        return await handler(request)

    return _test_task_context_decorator


@ensure_single_setup(__name__, logger=_logger)
def setup_long_running_tasks(app: web.Application) -> None:
    # register all long-running tasks from different modules
    register_projects_long_running_tasks(app)

    namespace_suffix = "TODO"  # TODO recover from settings

    setup(
        app,
        redis_settings=redis.get_plugin_settings(app),
        rabbit_settings=rabbitmq_settings.get_plugin_settings(app),
        redis_namespace=_get_namespace(namespace_suffix),
        rabbit_namespace=_get_namespace(namespace_suffix),
        router_prefix=f"/{API_VTAG}/tasks-legacy",
        handler_check_decorator=login_required,
        task_request_context_decorator=webserver_request_context_decorator,
    )
