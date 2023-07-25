# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter
from fastapi.responses import FileResponse
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
        "exporter",
    ],
)


@router.post(
    "/projects/{project_id}:xport",
    response_class=FileResponse,
    operation_id="export_project",
)
def export_project(project_id: str):
    """
    creates an archive of the project and downloads it
    """
