import logging
from functools import wraps

from aiohttp import web
from servicelib.aiohttp.long_running_tasks import (
    LONG_RUNNING_TASKS_CONTEXT_REQKEY,
)
from servicelib.aiohttp.long_running_tasks.server import setup
from servicelib.aiohttp.typing_extension import Handler

from .. import rabbitmq_settings, redis
from .._meta import API_VTAG, APP_NAME
from ..application_setup import ModuleCategory, app_setup_func
from ..login.decorators import login_required
from ..models import AuthenticatedRequestContext
from ..projects.plugin import register_projects_long_running_tasks
from . import settings as long_running_tasks_settings

_logger = logging.getLogger(__name__)


def _get_lrt_namespace(suffix: str) -> str:
    return f"{APP_NAME}-{suffix}"


def webserver_request_context_decorator(handler: Handler):
    @wraps(handler)
    async def _test_task_context_decorator(
        request: web.Request,
    ) -> web.StreamResponse:
        """this task context callback tries to get the user_id from the query if available"""
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        request[LONG_RUNNING_TASKS_CONTEXT_REQKEY] = req_ctx.model_dump(
            mode="json", by_alias=True
        )
        return await handler(request)

    return _test_task_context_decorator


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_LONG_RUNNING_TASKS",
    logger=_logger,
)
def setup_long_running_tasks(app: web.Application) -> None:
    # register all long-running tasks from different modules
    register_projects_long_running_tasks(app)

    settings = long_running_tasks_settings.get_plugin_settings(app)

    setup(
        app,
        redis_settings=redis.get_plugin_settings(app),
        rabbit_settings=rabbitmq_settings.get_plugin_settings(app),
        lrt_namespace=_get_lrt_namespace(settings.LONG_RUNNING_TASKS_NAMESPACE_SUFFIX),
        router_prefix=f"/{API_VTAG}/tasks-legacy",
        handler_check_decorator=login_required,
        task_request_context_decorator=webserver_request_context_decorator,
    )
