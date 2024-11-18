""" Handles request to the viewers redirection entrypoints

"""

import functools
import logging
import urllib.parse
from typing import TypeAlias

from aiohttp import web
from common_library.error_codes import create_error_code
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey, ServiceVersion
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.typing_extension import Handler
from servicelib.logging_errors import create_troubleshotting_log_kwargs

from ..director_v2.api import update_dynamic_service_networks_in_project
from ..products.api import get_product_name
from ..utils import compose_support_error_msg
from ..utils_aiohttp import create_redirect_to_page_response
from ._catalog import ValidService, validate_requested_service
from ._constants import MSG_UNEXPECTED_ERROR
from ._core import validate_requested_file, validate_requested_viewer
from ._errors import InvalidRedirectionParams, StudyDispatcherError
from ._models import FileParams, ServiceInfo, ServiceParams, ViewerInfo
from ._projects import (
    get_or_create_project_with_file,
    get_or_create_project_with_file_and_service,
    get_or_create_project_with_service,
)
from ._users import UserInfo, ensure_authentication, get_or_create_guest_user
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)

#
# HELPERS
#


def _create_redirect_response_to_view_page(
    app: web.Application,
    project_id: ProjectID,
    viewer_node_id: NodeID,
    file_name: str | None,
    file_size: int | str | None,
) -> web.HTTPFound:
    # NOTE: these are 'view' page params and need to be interpreted by front-end correctly!
    return create_redirect_to_page_response(
        app,
        page="view",
        project_id=f"{project_id}",
        viewer_node_id=f"{viewer_node_id}",
        file_name=file_name or "unkwnown",
        file_size=file_size or 0,
    )


def _create_redirect_response_to_error_page(
    app: web.Application, message: str, status_code: int
) -> web.HTTPFound:
    # NOTE: these are 'error' page params and need to be interpreted by front-end correctly!
    return create_redirect_to_page_response(
        app,
        page="error",
        message=message,
        status_code=status_code,
    )


def _create_service_info_from(service: ValidService) -> ServiceInfo:
    values_map = dict(
        key=service.key,
        version=service.version,
        label=service.title,
        is_guest_allowed=service.is_public,
    )
    if service.thumbnail:
        values_map["thumbnail"] = service.thumbnail
    return ServiceInfo.model_construct(_fields_set=set(values_map.keys()), **values_map)


def _handle_errors_with_error_page(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (web.HTTPRedirection, web.HTTPSuccessful):
            # NOTE: that response is a redirection that is reraised and not returned
            raise

        except StudyDispatcherError as err:
            raise _create_redirect_response_to_error_page(
                request.app,
                message=f"Sorry, we cannot dispatch your study: {err}",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,  # 422
            ) from err

        except web.HTTPUnauthorized as err:
            raise _create_redirect_response_to_error_page(
                request.app,
                message=f"{err.reason}. Please reload this page to login/register.",
                status_code=err.status_code,
            ) from err

        except web.HTTPUnprocessableEntity as err:
            raise _create_redirect_response_to_error_page(
                request.app,
                message=f"Invalid parameters in link: {err.reason}",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,  # 422
            ) from err

        except web.HTTPClientError as err:
            _logger.exception("Client error with status code %d", err.status_code)
            raise _create_redirect_response_to_error_page(
                request.app,
                message=err.reason,
                status_code=err.status_code,
            ) from err

        except (ValidationError, web.HTTPServerError, Exception) as err:
            error_code = create_error_code(err)

            user_error_msg = compose_support_error_msg(
                msg=MSG_UNEXPECTED_ERROR.format(hint=""), error_code=error_code
            )
            _logger.exception(
                **create_troubleshotting_log_kwargs(
                    user_error_msg,
                    error=err,
                    error_code=error_code,
                    error_context={"request": request},
                    tip="Unexpected failure while dispatching study",
                )
            )
            raise _create_redirect_response_to_error_page(
                request.app,
                message=user_error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from err

    return wrapper


#
# API Schemas
#


class ServiceQueryParams(ServiceParams):
    model_config = ConfigDict(extra="forbid")


class FileQueryParams(FileParams):
    model_config = ConfigDict(extra="forbid")

    @field_validator("file_type")
    @classmethod
    def ensure_extension_upper_and_dotless(cls, v):
        # NOTE: see filetype constraint-check
        if v and isinstance(v, str):
            w = urllib.parse.unquote(v)
            return w.upper().lstrip(".")
        return v


class ServiceAndFileParams(FileQueryParams, ServiceParams):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {"$ref": "#/definitions/FileParams"},
                {"$ref": "#/definitions/ServiceParams"},
            ]
        }
    )


class ViewerQueryParams(BaseModel):
    file_type: str | None = None
    viewer_key: ServiceKey
    viewer_version: ServiceVersion

    @staticmethod
    def from_viewer(viewer: ViewerInfo) -> "ViewerQueryParams":
        # can safely construct w/o validation from a viewer
        return ViewerQueryParams.model_construct(
            file_type=viewer.filetype,
            viewer_key=viewer.key,
            viewer_version=viewer.version,
        )

    @field_validator("file_type")
    @classmethod
    def ensure_extension_upper_and_dotless(cls, v):
        # NOTE: see filetype constraint-check
        if v and isinstance(v, str):
            w = urllib.parse.unquote(v)
            return w.upper().lstrip(".")
        return v


RedirectionQueryParams: TypeAlias = (
    # NOTE: Extra.forbid in FileQueryParams, ServiceQueryParams avoids bad casting when
    # errors in ServiceAndFileParams
    ServiceAndFileParams
    | FileQueryParams
    | ServiceQueryParams
)

#
# API HANDLERS
#


@_handle_errors_with_error_page
async def get_redirection_to_viewer(request: web.Request):
    """
    - validate request
    - get or create user
    - get or create project
    - create redirect response
    - create and set auth cookie

    NOTE: Can be set as login_required programatically with STUDIES_ACCESS_ANONYMOUS_ALLOWED env var.
    """
    query_params: RedirectionQueryParams = parse_request_query_parameters_as(
        RedirectionQueryParams, request  # type: ignore[arg-type] # from pydantic v2 --> https://github.com/pydantic/pydantic/discussions/4950
    )
    _logger.debug("Requesting viewer %s [%s]", query_params, type(query_params))

    user: UserInfo
    if isinstance(query_params, ServiceAndFileParams):
        file_params = service_params = query_params

        # NOTE: Cannot check file_size in from HEAD in a AWS download link so file_size is just infomative
        viewer: ViewerInfo = await validate_requested_viewer(
            request.app,
            file_type=file_params.file_type,
            file_size=file_params.file_size,
            service_key=service_params.viewer_key,
            service_version=service_params.viewer_version,
        )

        # Retrieve user or create a temporary guest
        user = await get_or_create_guest_user(
            request, allow_anonymous_or_guest_users=viewer.is_guest_allowed
        )

        # Generate one project per user + download_link + viewer
        project_id, viewer_id = await get_or_create_project_with_file_and_service(
            request.app,
            user,
            viewer,
            file_params.download_link,
            product_name=get_product_name(request),
        )
        await update_dynamic_service_networks_in_project(request.app, project_id)

        response = _create_redirect_response_to_view_page(
            request.app,
            project_id=project_id,
            viewer_node_id=viewer_id,
            file_name=file_params.file_name,
            file_size=file_params.file_size,
        )

    elif isinstance(query_params, ServiceQueryParams):
        service_params_ = query_params

        valid_service: ValidService = await validate_requested_service(
            app=request.app,
            service_key=service_params_.viewer_key,
            service_version=service_params_.viewer_version,
        )

        user = await get_or_create_guest_user(
            request, allow_anonymous_or_guest_users=valid_service.is_public
        )

        project_id, viewer_id = await get_or_create_project_with_service(
            request.app,
            user,
            service_info=_create_service_info_from(valid_service),
            product_name=get_product_name(request),
        )
        await update_dynamic_service_networks_in_project(request.app, project_id)

        response = _create_redirect_response_to_view_page(
            request.app,
            project_id=project_id,
            viewer_node_id=viewer_id,
            file_name="none",
            file_size=0,
        )

    elif isinstance(query_params, FileQueryParams):
        file_params_ = query_params

        validate_requested_file(
            app=request.app,
            file_type=file_params_.file_type,
            file_size=file_params_.file_size,
        )

        # NOTE: file-only dispatch is reserved to registered users
        # - Anonymous user rights associated with services, not files
        # - Front-end viewer for anonymous users cannot render a single file-picker. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4342
        # - Risk of anonymous users to polute platform with data
        user = await get_or_create_guest_user(
            request, allow_anonymous_or_guest_users=False
        )

        project_id, file_picker_id = await get_or_create_project_with_file(
            request.app,
            user,
            file_params=file_params_,
            project_thumbnail=get_plugin_settings(
                app=request.app
            ).STUDIES_DEFAULT_FILE_THUMBNAIL,
            product_name=get_product_name(request),
        )
        await update_dynamic_service_networks_in_project(request.app, project_id)

        response = _create_redirect_response_to_view_page(
            request.app,
            project_id=project_id,
            viewer_node_id=file_picker_id,  # TODO: ask odei about this?
            file_name=file_params_.file_name,
            file_size=file_params_.file_size,
        )

    else:
        # NOTE: if query is done right, this should never happen
        raise InvalidRedirectionParams()

    # Adds auth cookies (login)
    await ensure_authentication(user, request, response)

    _logger.debug(
        "Response with redirect '%s' w/ auth cookie in headers %s)",
        response,
        response.headers,
    )

    # NOTE: Why raising the response?
    #  SEE aiohttp/web_protocol.py: DeprecationWarning: returning HTTPException object is deprecated (#2415) and will be removed, please raise the exception instead
    assert isinstance(response, web.HTTPFound)  # nosec
    raise response
