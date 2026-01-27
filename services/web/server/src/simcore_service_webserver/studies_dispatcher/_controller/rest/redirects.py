"""Handles request to the viewers redirection entrypoints"""

import logging

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as

from ....db.plugin import get_asyncpg_engine
from ....dynamic_scheduler import api as dynamic_scheduler_service
from ....products import products_web
from ....utils_aiohttp import create_redirect_to_page_response, get_api_base_url
from ... import _service
from ..._catalog import ValidService, validate_requested_service
from ..._errors import (
    InvalidRedirectionParamsError,
)
from ..._models import ServiceInfo, ViewerInfo
from ..._projects import (
    get_or_create_project_with_file,
    get_or_create_project_with_file_and_service,
    get_or_create_project_with_service,
)
from ..._users import UserInfo, ensure_authentication, get_or_create_guest_user
from ...settings import get_plugin_settings
from .redirects_exceptions import handle_errors_with_error_page
from .redirects_schemas import (
    FileQueryParams,
    RedirectionQueryParams,
    ServiceAndFileParams,
    ServiceQueryParams,
)

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


def _create_service_info_from(service: ValidService) -> ServiceInfo:
    values_map = {
        "key": service.key,
        "version": service.version,
        "label": service.title,
        "is_guest_allowed": service.is_public,
    }
    if service.thumbnail:
        values_map["thumbnail"] = service.thumbnail
    return ServiceInfo.model_construct(_fields_set=set(values_map.keys()), **values_map)


#
# ROUTES
#


@handle_errors_with_error_page
async def get_redirection_to_viewer(request: web.Request):
    """
    - validate request
    - get or create user
    - get or create project
    - create redirect response
    - create and set auth cookie

    NOTE: Can be set as login_required programmatically with STUDIES_ACCESS_ANONYMOUS_ALLOWED env var.
    """
    query_params: RedirectionQueryParams = parse_request_query_parameters_as(
        RedirectionQueryParams,
        request,  # type: ignore[arg-type] # from pydantic v2 --> https://github.com/pydantic/pydantic/discussions/4950
    )
    _logger.debug("Requesting viewer %s [%s]", query_params, type(query_params))

    user: UserInfo
    if isinstance(query_params, ServiceAndFileParams):
        file_params = service_params = query_params

        # NOTE: Cannot check file_size in from HEAD in a AWS download link so file_size is just infomative
        viewer: ViewerInfo = await _service.validate_requested_viewer(
            request.app,
            file_type=file_params.file_type,
            file_size=file_params.file_size,
            service_key=service_params.viewer_key,
            service_version=service_params.viewer_version,
        )

        # Retrieve user or create a temporary guest
        user = await get_or_create_guest_user(request, allow_anonymous_or_guest_users=viewer.is_guest_allowed)

        # Generate one project per user + download_link + viewer
        project_id, viewer_id = await get_or_create_project_with_file_and_service(
            request.app,
            user,
            viewer,
            file_params.download_link,
            product_name=products_web.get_product_name(request),
            product_api_base_url=get_api_base_url(request),
        )
        await dynamic_scheduler_service.update_projects_networks(request.app, project_id=project_id)

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
            get_asyncpg_engine(request.app),
            service_key=service_params_.viewer_key,
            service_version=service_params_.viewer_version,
        )

        user = await get_or_create_guest_user(request, allow_anonymous_or_guest_users=valid_service.is_public)

        project_id, viewer_id = await get_or_create_project_with_service(
            request.app,
            user,
            service_info=_create_service_info_from(valid_service),
            product_name=products_web.get_product_name(request),
            product_api_base_url=get_api_base_url(request),
        )
        await dynamic_scheduler_service.update_projects_networks(request.app, project_id=project_id)

        response = _create_redirect_response_to_view_page(
            request.app,
            project_id=project_id,
            viewer_node_id=viewer_id,
            file_name="none",
            file_size=0,
        )

    elif isinstance(query_params, FileQueryParams):
        file_params_ = query_params

        _service.validate_requested_file(
            app=request.app,
            file_type=file_params_.file_type,
            file_size=file_params_.file_size,
        )

        # NOTE: file-only dispatch is reserved to registered users
        # - Anonymous user rights associated with services, not files
        # - Front-end viewer for anonymous users cannot render a single file-picker. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4342
        # - Risk of anonymous users to pollute platform with data
        user = await get_or_create_guest_user(request, allow_anonymous_or_guest_users=False)

        project_id, file_picker_id = await get_or_create_project_with_file(
            request.app,
            user,
            file_params=file_params_,
            project_thumbnail=get_plugin_settings(app=request.app).STUDIES_DEFAULT_FILE_THUMBNAIL,
            product_name=products_web.get_product_name(request),
            product_api_base_url=get_api_base_url(request),
        )
        await dynamic_scheduler_service.update_projects_networks(request.app, project_id=project_id)

        response = _create_redirect_response_to_view_page(
            request.app,
            project_id=project_id,
            viewer_node_id=file_picker_id,  # TODO: ask odei about this?
            file_name=file_params_.file_name,
            file_size=file_params_.file_size,
        )

    else:
        # NOTE: if query is done right, this should never happen
        raise InvalidRedirectionParamsError(query_params=query_params)

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
