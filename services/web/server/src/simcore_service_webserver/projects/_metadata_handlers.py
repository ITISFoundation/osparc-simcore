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

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required

routes = web.RouteTableDef()


#
# projects/*/job-metadata
#


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/job-metadata", name="get_project_job_metadata"
)
@login_required
@permission_required("project.read")
async def get_project_job_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError


@routes.patch(
    f"/{VTAG}/projects/{{project_id}}/job-metadata", name="create_project_job_metadata"
)
@login_required
@permission_required("project.create")
async def update_project_job_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError


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
    raise NotImplementedError


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/custom-metadata",
    name="update_project_custom_metadata",
)
@login_required
@permission_required("project.update")
async def update_project_custom_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError
