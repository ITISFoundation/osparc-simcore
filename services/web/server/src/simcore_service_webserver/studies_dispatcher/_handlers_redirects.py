""" Handles request to the viewers redirection entrypoints

"""
import functools
import logging
import urllib.parse

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
    get_or_create_project_with_file,
    get_or_create_project_with_file_and_service,
    get_or_create_project_with_service,
)
from ._users import UserInfo, ensure_authentication, get_or_create_user
from .settings import StudiesDispatcherSettings, get_plugin_settings

_logger = logging.getLogger(__name__)
_SPACE = " "


#
# API Models
#


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
    """
    - validate request
    - acquire user
    - acquire project
    - create_redirect_response
    - ensure_authentication
    """
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
        user: UserInfo = await get_or_create_user(
            request, is_guest_allowed=viewer.is_guest_allowed
        )

        # Generate one project per user + download_link + viewer
        project_id, viewer_id = await get_or_create_project_with_file_and_service(
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

    elif service_params:

        valid_service = await validate_requested_service(
            app=request.app,
            service_key=service_params.viewer_key,
            service_version=service_params.viewer_version,
        )

        # Retrieve user or create a temporary guest
        user: UserInfo = await get_or_create_user(
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

        project_id, viewer_id = await get_or_create_project_with_service(
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

    elif file_params:

        # TODO: validate_requested_file ??!!

        user: UserInfo = await get_or_create_user(request, is_guest_allowed=False)

        settings: StudiesDispatcherSettings = get_plugin_settings(app=request.app)

        project_id, file_picker_id = await get_or_create_project_with_file(
            request.app,
            user,
            file_params=file_params,
            project_thumbnail=settings.STUDIES_DEFAULT_DATA_THUMBNAIL,
            product_name=get_product_name(request),
        )

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

    else:
        # NOTE: if query is done right, this should never happen
        raise StudyDispatcherError(reason=MSG_INVALID_REDIRECTION_PARAMS_ERROR)

    # lastly, ensure auth if any
    await ensure_authentication(user, request, response)

    _logger.debug(
        "Response with redirect '%s' w/ auth cookie in headers %s)",
        response,
        response.headers,
    )

    return response
