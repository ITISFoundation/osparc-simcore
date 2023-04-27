""" Handles request to the viewers redirection entrypoints

"""
import functools
import logging
import urllib.parse
from typing import cast

from aiohttp import web
from models_library.services import ServiceKey, ServiceVersion
from models_library.utils.pydantic_tools_extension import parse_obj_or_none
from pydantic import BaseModel, HttpUrl, ValidationError, root_validator, validator
from pydantic.types import PositiveInt
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.typing_extension import Handler
from servicelib.error_codes import create_error_code

from ..products.plugin import get_product_name
from ..utils import compose_support_error_msg
from ..utils_aiohttp import create_redirect_response
from ._catalog import validate_requested_service
from ._constants import MSG_INVALID_REDIRECTION_PARAMS_ERROR, MSG_UNEXPECTED_ERROR
from ._core import StudyDispatcherError, ViewerInfo, validate_requested_viewer
from ._models import FileParams, ServiceInfo, ServiceParams
from ._projects import (
    acquire_project_with_file,
    acquire_project_with_service,
    acquire_project_with_viewer,
)
from ._users import UserInfo, acquire_user, ensure_authentication

_logger = logging.getLogger(__name__)
_SPACE = " "


class ViewerQueryParams(BaseModel):
    file_type: str | None = None
    viewer_key: ServiceKey
    viewer_version: ServiceVersion

    @staticmethod
    def from_viewer(viewer: ViewerInfo) -> "ViewerQueryParams":
        # can safely construct w/o validation from a viewer
        return ViewerQueryParams.construct(
            file_type=viewer.filetype,
            viewer_key=viewer.key,
            viewer_version=viewer.version,
        )

    @validator("file_type")
    @classmethod
    def ensure_extension_upper_and_dotless(cls, v):
        # NOTE: see filetype constraint-check
        if v and isinstance(v, str):
            w = urllib.parse.unquote(v)
            return w.upper().lstrip(".")
        return v


class RedirectionQueryParams(ViewerQueryParams):
    file_name: str = "unknown"
    file_size: PositiveInt | None = None
    download_link: HttpUrl | None = None

    @validator("download_link", pre=True)
    @classmethod
    def unquote_url(cls, v):
        # NOTE: see test_url_quoting_and_validation
        # before any change here
        if v:
            w = urllib.parse.unquote(v)
            if _SPACE in w:
                w = w.replace(_SPACE, "%20")
            return w
        return v

    @root_validator
    @classmethod
    def file_params_required(cls, values):
        # A service only does not need file info
        # If some file-info then
        file_type = values.get("file_type")
        download_link = values.get("download_link")
        file_size = values.get("file_size")

        file_params = (file_type, download_link, file_size)

        if all(p is None for p in file_params) or all(
            p is not None for p in file_params
        ):
            return values

        raise ValueError("One or more file parameters missing")

    class Config:
        schema_extra = {
            "examples": [
                {
                    "viewer_key": "simcore/services/comp/foo",
                    "viewer_version": "1.2.3",
                    "file_type": "lowerUPPER",
                    "file_name": "filename",
                    "file_size": "12",
                    "download_link": "https://download.io/file123",
                }
            ]
        }


def compose_dispatcher_prefix_url(request: web.Request, viewer: ViewerInfo) -> HttpUrl:
    """This is denoted PREFIX URL because it needs to append extra query
    parameters added in RedirectionQueryParams
    """
    params = ViewerQueryParams.from_viewer(viewer).dict()
    absolute_url = request.url.join(
        request.app.router["get_redirection_to_viewer"].url_for().with_query(**params)
    )
    return cast(HttpUrl, f"{absolute_url}")


def compose_service_dispatcher_prefix_url(
    request: web.Request, service_key: str, service_version: str
) -> HttpUrl:
    params = ViewerQueryParams(
        viewer_key=service_key, viewer_version=service_version  # type: ignore
    ).dict(exclude_none=True, exclude_unset=True)
    absolute_url = request.url.join(
        request.app.router["get_redirection_to_viewer"].url_for().with_query(**params)
    )
    return cast(HttpUrl, f"{absolute_url}")


def _handle_errors_with_error_page(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except StudyDispatcherError as err:
            raise create_redirect_response(
                request.app,
                page="error",
                message=f"Sorry, we cannot view this file: {err.reason}",
                status_code=web.HTTPUnprocessableEntity.status_code,  # 422
            ) from err

        except web.HTTPUnauthorized as err:
            raise create_redirect_response(
                request.app,
                page="error",
                message=f"{err.reason}. Please reload this page to login/register.",
                status_code=err.status_code,
            ) from err

        except web.HTTPUnprocessableEntity as err:
            raise create_redirect_response(
                request.app,
                page="error",
                message=f"Invalid parameters in link: {err.reason}",
                status_code=web.HTTPUnprocessableEntity.status_code,  # 422
            ) from err

        except web.HTTPClientError as err:
            _logger.exception("Client error with status code %d", err.status_code)
            raise create_redirect_response(
                request.app,
                page="error",
                message=err.reason,
                status_code=err.status_code,
            ) from err

        except (ValidationError, web.HTTPServerError, Exception) as err:
            error_code = create_error_code(err)
            _logger.exception(
                "Unexpected failure while dispatching study [%s]",
                f"{error_code}",
                extra={"error_code": error_code},
            )
            raise create_redirect_response(
                request.app,
                page="error",
                message=compose_support_error_msg(
                    msg=MSG_UNEXPECTED_ERROR.format(hint=""), error_code=error_code
                ),
                status_code=500,
            ) from err

    return wrapper


@_handle_errors_with_error_page
async def get_redirection_to_viewer(request: web.Request):
    query_params = parse_request_query_parameters_as(RedirectionQueryParams, request)

    _logger.debug("Requesting viewer %s", query_params)

    file_params = parse_obj_or_none(FileParams, query_params)
    service_params = parse_obj_or_none(ServiceParams, query_params)

    if file_params and service_params:
        # TODO: Cannot check file_size from HEAD
        # removed await params.check_download_link()
        # Perhaps can check the header for GET while downloading and retreive file_size??
        viewer: ViewerInfo = await validate_requested_viewer(
            request.app,
            file_type=file_params.file_type,
            file_size=file_params.file_size,
            service_key=service_params.viewer_key,
            service_version=service_params.viewer_version,
        )

        # Retrieve user or create a temporary guest
        user: UserInfo = await acquire_user(
            request, is_guest_allowed=viewer.is_guest_allowed
        )

        # Generate one project per user + download_link + viewer
        project_id, viewer_id = await acquire_project_with_viewer(
            request.app,
            user,
            viewer,
            file_params.download_link,
            product_name=get_product_name(request),
        )

        # Redirection and creation of cookies (for guests)
        # Produces  /#/view?project_id= & viewer_node_id
        response = create_redirect_response(
            request.app,
            page="view",
            project_id=project_id,
            viewer_node_id=viewer_id,
            file_name=file_params.file_name or "unkwnown",
            file_size=file_params.file_size,
        )

        # lastly, ensure auth if any
        await ensure_authentication(user, request, response)

    elif service_params:

        valid_service = await validate_requested_service(
            app=request.app,
            service_key=service_params.viewer_key,
            service_version=service_params.viewer_version,
        )

        # Retrieve user or create a temporary guest
        user: UserInfo = await acquire_user(
            request, is_guest_allowed=valid_service.is_public
        )

        values_map = dict(
            key=valid_service.key,
            version=valid_service.version,
            label=valid_service.title,
            is_guest_allowed=valid_service.is_public,
        )
        if valid_service.thumbnail:
            values_map["thumbnail"] = valid_service.thumbnail

        project_id, viewer_id = await acquire_project_with_service(
            request.app,
            user,
            service_info=ServiceInfo.construct(
                _fields_set=set(values_map.keys()), **values_map
            ),
            product_name=get_product_name(request),
        )
        _logger.debug("Project acquired '%s'", project_id)

        response = create_redirect_response(
            request.app,
            page="view",
            project_id=project_id,
            viewer_node_id=viewer_id,
            file_name="none",
            file_size=0,
        )

        await ensure_authentication(user, request, response)

    elif file_params:
        # Retrieve user or create a temporary guest
        user: UserInfo = await acquire_user(request, is_guest_allowed=False)

        project_id, file_picker_id = await acquire_project_with_file(
            request.app,
            user,
            params=file_params,
            thumbnail="",
            product_name=get_product_name(request),
        )
        _logger.debug("Project acquired '%s'", project_id)

        # Retrieve user or create a temporary guest
        user: UserInfo = await acquire_user(request, is_guest_allowed=False)

        # Redirection and creation of cookies (for guests)
        # Produces  /#/view?project_id= & viewer_node_id
        response = create_redirect_response(
            request.app,
            page="view",
            project_id=project_id,
            viewer_node_id=file_picker_id,  # FIXME!!!
            file_name=file_params.file_name or "unkwnown",
            file_size=file_params.file_size,
        )

        # lastly, ensure auth if any
        await ensure_authentication(user, request, response)
    else:
        raise StudyDispatcherError(reason=MSG_INVALID_REDIRECTION_PARAMS_ERROR)

    _logger.debug(
        "Response with redirect '%s' w/ auth cookie in headers %s)",
        response,
        response.headers,
    )

    return response
