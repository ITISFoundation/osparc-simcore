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

#
# EXCEPTIONS HANDLING
#


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


#
# ROUTES
#

routes = web.RouteTableDef()


@routes.delete(f"/{VTAG}/trash", name="empty_trash")
@login_required
@permission_required("project.delete")
@_handle_exceptions
async def empty_trash(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)

    fire_and_forget_task(
        _service.empty_trash_safe(
            request.app, product_name=product_name, user_id=user_id
        ),
        task_suffix_name="rest.empty_trash",
        fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
