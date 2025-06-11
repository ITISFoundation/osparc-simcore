"""

Design rationale:

- Resource metadata/labels: https://cloud.google.com/apis/design/design_patterns#resource_labels
    - named `metadata` instead of labels
    - limit number of entries and depth? dict[str, st] ??
- Singleton https://cloud.google.com/apis/design/design_patterns#singleton_resources
    - the singleton is implicitly created or deleted when its parent is created or deleted
    - Get and Update methods only
"""

import logging

from aiohttp import web
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.logging_utils import log_catch

from ..._meta import api_version_prefix
from ...login.decorators import login_required
from ...security.decorators import permission_required
from ...utils_aiohttp import envelope_json_response
from .. import _metadata_service
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import AuthenticatedRequestContext, ProjectPathParams

routes = web.RouteTableDef()

_logger = logging.getLogger(__name__)


@routes.get(
    f"/{api_version_prefix}/projects/{{project_id}}/metadata",
    name="get_project_metadata",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_metadata(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    custom_metadata = await _metadata_service.get_project_custom_metadata_for_user(
        request.app, user_id=req_ctx.user_id, project_uuid=path_params.project_id
    )

    return envelope_json_response(
        ProjectMetadataGet(project_uuid=path_params.project_id, custom=custom_metadata)
    )


@routes.patch(
    f"/{api_version_prefix}/projects/{{project_id}}/metadata",
    name="update_project_metadata",
)
@login_required
@permission_required("project.update")
@handle_plugin_requests_exceptions
async def update_project_metadata(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    update = await parse_request_body_as(ProjectMetadataUpdate, request)

    custom_metadata = await _metadata_service.set_project_custom_metadata(
        request.app,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        value=update.custom,
    )
    with log_catch(_logger, reraise=False):
        await _metadata_service.set_project_ancestors_from_custom_metadata(
            request.app,
            user_id=req_ctx.user_id,
            project_uuid=path_params.project_id,
            custom_metadata=custom_metadata,
        )

    return envelope_json_response(
        ProjectMetadataGet(project_uuid=path_params.project_id, custom=custom_metadata)
    )
