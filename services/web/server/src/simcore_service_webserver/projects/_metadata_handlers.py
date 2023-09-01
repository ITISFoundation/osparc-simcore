"""

Design rationale:

- Resource metadata/labels: https://cloud.google.com/apis/design/design_patterns#resource_labels
	- named `metadata` instead of labels
	- limit number of entries and depth? dict[str, st] ??
- Singleton https://cloud.google.com/apis/design/design_patterns#singleton_resources
	- the singleton is implicitly created or deleted when its parent is created or deleted
	- Get and Update methods only
"""


import functools

from aiohttp import web
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler

from .._meta import api_version_prefix
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _metadata_api
from ._common_models import ProjectPathParams, RequestContext
from .exceptions import ProjectInvalidRightsError, ProjectNotFoundError

routes = web.RouteTableDef()


def _handle_project_exceptions(handler: Handler):
    """Transforms project errors -> http errors"""

    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ProjectNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc
        except ProjectInvalidRightsError as exc:
            raise web.HTTPUnauthorized(reason=f"{exc}") from exc

    return wrapper


#
# projects/*/custom-metadata
#


@routes.get(
    f"/{api_version_prefix}/projects/{{project_id}}/metadata",
    name="get_project_metadata",
)
@login_required
@permission_required("project.read")
@_handle_project_exceptions
async def get_project_metadata(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    custom_metadata = await _metadata_api.get_project_metadata(
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
@_handle_project_exceptions
async def update_project_metadata(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    update = await parse_request_body_as(ProjectMetadataUpdate, request)

    custom_metadata = await _metadata_api.set_project_custom_metadata(
        request.app,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        value=update.custom,
    )

    return envelope_json_response(
        ProjectMetadataGet(project_uuid=path_params.project_id, custom=custom_metadata)
    )
