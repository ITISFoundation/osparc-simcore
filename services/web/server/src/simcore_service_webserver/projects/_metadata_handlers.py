from aiohttp import web

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required

routes = web.RouteTableDef()


#
# projects/*/job-metadata
#


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/job-metadata", name="create_project_job_metadata"
)
@login_required
@permission_required("project.create")
async def create_project_job_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/job-metadata", name="get_project_job_metadata"
)
@login_required
@permission_required("project.read")
async def get_project_job_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError


@routes.get(f"/{VTAG}/projects/-/job-metadata", name="list_projects_job_metadata")
@login_required
@permission_required("project.read")
async def list_projects_job_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError


#
# projects/*/custom-metadata
#


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/custom-metadata",
    name="create_project_custom_metadata",
)
@login_required
@permission_required("project.create")
async def create_project_custom_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/custom-metadata",
    name="get_project_custom_metadata",
)
@login_required
@permission_required("project.read")
async def get_project_custom_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError


@routes.patch(
    f"/{VTAG}/projects/{{project_id}}/custom-metadata",
    name="update_project_custom_metadata",
)
@login_required
@permission_required("project.update")
async def update_project_custom_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError


@routes.delete(
    f"/{VTAG}/projects/{{project_id}}/custom-metadata",
    name="update_project_custom_metadata",
)
@login_required
@permission_required("project.delete")
async def delete_project_custom_metadata(request: web.Request) -> web.Response:
    raise NotImplementedError
