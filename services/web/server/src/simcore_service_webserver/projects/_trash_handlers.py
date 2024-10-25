import functools
import logging
from typing import NamedTuple

from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.aiohttp.web_exceptions_extension import get_http_error_class_or_none
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error

from .._meta import API_VTAG as VTAG
from ..login.decorators import get_user_id, login_required
from ..products.api import get_product_name
from ..projects._common_models import ProjectPathParams
from ..security.decorators import permission_required
from . import _trash_api
from ._common_models import RemoveQueryParams
from .exceptions import (
    ProjectRunningConflictError,
    ProjectStoppingError,
    ProjectTrashError,
)

_logger = logging.getLogger(__name__)

#
# EXCEPTIONS HANDLING
#


class HttpErrorInfo(NamedTuple):
    status_code: int
    msg_template: str


_TO_HTTP_ERROR_MAP: dict[type[Exception], HttpErrorInfo] = {
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Current study is in use and cannot be trashed [{project_uuid}]. Please stop all services first and try again",
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Something went wrong while stopping services before trashing. Aborting trash.",
    ),
}


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


def _handle_request_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def _wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ProjectTrashError as exc:
            for exc_cls, http_error_info in _TO_HTTP_ERROR_MAP.items():
                if isinstance(exc, exc_cls):

                    # safe formatting, i.e. does not raise
                    user_msg = http_error_info.msg_template.format_map(
                        _DefaultDict(getattr(exc, "__dict__", {}))
                    )

                    http_error_cls = get_http_error_class_or_none(
                        http_error_info.status_code
                    )
                    assert http_error_cls  # nosec

                    if is_5xx_server_error(http_error_info.status_code):
                        _logger.exception(
                            **create_troubleshotting_log_kwargs(
                                user_msg,
                                error=exc,
                                error_context={
                                    "request": request,
                                    "request.remote": f"{request.remote}",
                                    "request.method": f"{request.method}",
                                    "request.path": f"{request.path}",
                                },
                            )
                        )
                    raise http_error_cls(reason=user_msg) from exc
            raise

    return _wrapper


#
# ROUTES
#

routes = web.RouteTableDef()


@routes.delete(f"/{VTAG}/trash", name="empty_trash")
@login_required
@permission_required("project.delete")
@_handle_request_exceptions
async def empty_trash(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)

    await _trash_api.empty_trash(
        request.app, product_name=product_name, user_id=user_id
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{VTAG}/projects/{{project_id}}:trash", name="trash_project")
@login_required
@permission_required("project.delete")
@_handle_request_exceptions
async def trash_project(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    query_params: RemoveQueryParams = parse_request_query_parameters_as(
        RemoveQueryParams, request
    )

    await _trash_api.trash_project(
        request.app,
        product_name=product_name,
        user_id=user_id,
        project_id=path_params.project_id,
        force_stop_first=query_params.force,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{VTAG}/projects/{{project_id}}:untrash", name="untrash_project")
@login_required
@permission_required("project.delete")
@_handle_request_exceptions
async def untrash_project(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    await _trash_api.untrash_project(
        request.app,
        product_name=product_name,
        user_id=user_id,
        project_id=path_params.project_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
