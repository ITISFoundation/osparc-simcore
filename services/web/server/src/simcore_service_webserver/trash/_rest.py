import asyncio
import logging

from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.utils import fire_and_forget_task

from .._meta import API_VTAG as VTAG
from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..login.decorators import get_user_id, login_required
from ..products.api import get_product_name
from ..projects.exceptions import ProjectRunningConflictError, ProjectStoppingError
from ..security.decorators import permission_required
from . import _service

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Current study is in use and cannot be trashed [project_id={project_uuid}]. Please stop all services first and try again",
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Something went wrong while stopping services before trashing. Aborting trash.",
    ),
}


_handle_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/trash:empty", name="empty_trash")
@login_required
@permission_required("project.delete")
@_handle_exceptions
async def empty_trash(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)

    is_running = asyncio.Event()

    async def _run():
        is_running.set()
        await _service.safe_empty_trash(
            request.app, product_name=product_name, user_id=user_id
        )

    fire_and_forget_task(
        _run(),
        task_suffix_name="rest.empty_trash",
        fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )

    # NOTE: Ensures `fire_and_forget_task` is triggered; otherwise,
    # when the front-end requests the trash item list,
    # it may still display items, misleading the user into
    # thinking the `empty trash` operation failed.
    await is_running.wait()

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
