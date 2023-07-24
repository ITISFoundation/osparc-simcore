# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
        "tags",
    ],
)


@router.put(
    "/projects/{study_uuid}/tags/{tag_id}",
    response_model=ProjectsStudyUuidTagsTagIdPutResponse,
    responses={"default": {"model": ProjectsStudyUuidTagsTagIdPutResponse1}},
)
def add_tag(
    tag_id: int, study_uuid: str = ...
) -> ProjectsStudyUuidTagsTagIdPutResponse | ProjectsStudyUuidTagsTagIdPutResponse1:
    """
    Links an existing label with an existing study
    """
    pass


@router.delete(
    "/projects/{study_uuid}/tags/{tag_id}",
    response_model=ProjectsStudyUuidTagsTagIdDeleteResponse,
    responses={"default": {"model": ProjectsStudyUuidTagsTagIdDeleteResponse1}},
)
def remove_tag(
    tag_id: int, study_uuid: str = ...
) -> (
    ProjectsStudyUuidTagsTagIdDeleteResponse | ProjectsStudyUuidTagsTagIdDeleteResponse1
):
    """
    Removes an existing link between a label and a study
    """
    pass
