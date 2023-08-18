# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.generics import Envelope
from models_library.projects import ProjectID
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
        "tags",
    ],
)


@router.put(
    "/projects/{project_uuid}/tags/{tag_id}",
    response_model=Envelope[ProjectGet],
)
def add_tag(
    project_uuid: ProjectID,
    tag_id: int,
):
    """
    Links an existing label with an existing study
    """


@router.delete(
    "/projects/{project_uuid}/tags/{tag_id}",
    response_model=Envelope[ProjectGet],
)
def remove_tag(
    project_uuid: ProjectID,
    tag_id: int,
):
    """
    Removes an existing link between a label and a study
    """
