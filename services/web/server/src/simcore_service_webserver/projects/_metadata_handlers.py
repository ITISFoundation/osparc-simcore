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

from .._meta import api_version_prefix
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _metadata_api
from ._common.exception_handlers import handle_plugin_requests_exceptions
from ._common.models import ProjectPathParams, RequestContext

routes = web.RouteTableDef()

_logger = logging.getLogger(__name__)


#
# projects/*/custom-metadata
#


@routes.get(
    f"/{api_version_prefix}/projects/{{project_id}}/metadata",
    name="get_project_metadata",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_metadata(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    custom_metadata = await _metadata_api.get_project_custom_metadata(
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
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    update = await parse_request_body_as(ProjectMetadataUpdate, request)

    custom_metadata = await _metadata_api.set_project_custom_metadata(
        request.app,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        value=update.custom,
    )
    with log_catch(_logger, reraise=False):
        await _metadata_api.set_project_ancestors_from_custom_metadata(
            request.app,
            user_id=req_ctx.user_id,
            project_uuid=path_params.project_id,
            custom_metadata=custom_metadata,
        )

    return envelope_json_response(
        ProjectMetadataGet(project_uuid=path_params.project_id, custom=custom_metadata)
    )
