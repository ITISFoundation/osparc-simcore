"""

Design rationale:

- Resource metadata/labels: https://cloud.google.com/apis/design/design_patterns#resource_labels
	- named `metadata` instead of labels
	- limit number of entries and depth? dict[str, st] ??
- Singleton https://cloud.google.com/apis/design/design_patterns#singleton_resources
	- the singleton is implicitly created or deleted when its parent is created or deleted
	- Get and Update methods only
"""


from aiohttp import web
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectCustomMetadataGet,
    ProjectCustomMetadataReplace,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from simcore_service_webserver.utils_aiohttp import envelope_json_response

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from . import _metadata_api
from ._common_models import ProjectPathParams, RequestContext

routes = web.RouteTableDef()


#
# projects/*/custom-metadata
#


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/custom-metadata",
    name="get_project_custom_metadata",
)
@login_required
@permission_required("project.read")
async def get_project_custom_metadata(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    custom_metadata = await _metadata_api.get_project_custom_metadata(
        request.app, user_id=req_ctx.user_id, project_id=path_params.project_id
    )

    return envelope_json_response(
        ProjectCustomMetadataGet(
            project_uuid=path_params.project_id, metadata=custom_metadata
        )
    )


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/custom-metadata",
    name="replace_project_custom_metadata",
)
@login_required
@permission_required("project.update")
async def replace_project_custom_metadata(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    new_metadata = await parse_request_body_as(ProjectCustomMetadataReplace, request)

    custom_metadata = await _metadata_api.set_project_custom_metadata(
        request.app,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        value=new_metadata,
    )

    return envelope_json_response(
        ProjectCustomMetadataGet(
            project_uuid=path_params.project_id, metadata=custom_metadata
        )
    )
