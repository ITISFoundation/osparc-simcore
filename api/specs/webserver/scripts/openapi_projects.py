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
    ],
)


@router.post(
    "/projects/{project_id}:open",
    response_model=ProjectsProjectIdOpenPostResponse,
    responses={"default": {"model": ProjectsProjectIdOpenPostResponse1}},
)
def open_project(
    project_id: str, body: str = ...
) -> ProjectsProjectIdOpenPostResponse | ProjectsProjectIdOpenPostResponse1:
    """
    Open a given project
    """
    pass


@router.post(
    "/projects/{project_id}:close",
    response_model=None,
    responses={"default": {"model": ProjectsProjectIdClosePostResponse}},
)
def close_project(
    project_id: str, body: str = ...
) -> None | ProjectsProjectIdClosePostResponse:
    """
    Closes a given project
    """
    pass


@router.get(
    "/projects/{project_id}/state",
    response_model=ProjectsProjectIdStateGetResponse,
    responses={"default": {"model": ProjectsProjectIdStateGetResponse1}},
)
def get_project_state(
    project_id: str,
) -> ProjectsProjectIdStateGetResponse | ProjectsProjectIdStateGetResponse1:
    """
    returns the state of a project
    """
    pass
