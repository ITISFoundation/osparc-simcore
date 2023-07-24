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
        "metamodeling",
    ],
)


@router.get(
    "/projects/{project_uuid}/checkpoint/{ref_id}/iterations",
    response_model=ProjectsProjectUuidCheckpointRefIdIterationsGetResponse,
    responses={
        "422": {"model": ProjectsProjectUuidCheckpointRefIdIterationsGetResponse1}
    },
    tags=["meta-projects"],
)
def simcore_service_webserver_meta_modeling_handlers__list_meta_project_iterations_handler(
    project_uuid: UUID,
    ref_id: Any = ...,
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=50)] = 20,
) -> (
    ProjectsProjectUuidCheckpointRefIdIterationsGetResponse
    | ProjectsProjectUuidCheckpointRefIdIterationsGetResponse1
):
    """
    List Project Iterations
    """
    pass


@router.get(
    "/projects/{project_uuid}/checkpoint/{ref_id}/iterations/-/results",
    response_model=ProjectsProjectUuidCheckpointRefIdIterationsResultsGetResponse,
    responses={
        "422": {
            "model": ProjectsProjectUuidCheckpointRefIdIterationsResultsGetResponse1
        }
    },
    tags=["meta-projects"],
)
def simcore_service_webserver_meta_modeling_handlers__list_meta_project_iterations_results_handler(
    project_uuid: UUID,
    ref_id: Any = ...,
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=50)] = 20,
) -> (
    ProjectsProjectUuidCheckpointRefIdIterationsResultsGetResponse
    | ProjectsProjectUuidCheckpointRefIdIterationsResultsGetResponse1
):
    """
    List Project Iterations Results
    """
    pass


@router.get(
    "/projects/{project_uuid}/checkpoint/{ref_id}/iterations/{iter_id}",
    response_model=None,
    tags=["meta-projects"],
)
def simcore_service_webserver_meta_modeling_handlers__get_meta_project_iterations_handler(
    project_uuid: UUID, ref_id: Any = ..., iter_id: int = ...
) -> None:
    """
    Get Project Iterations
    """
    pass


@router.get(
    "/projects/{project_uuid}/checkpoint/{ref_id}/iterations/{iter_id}/results",
    response_model=None,
    tags=["meta-projects"],
)
def simcore_service_webserver_meta_modeling_handlers__get_meta_project_iteration_results_handler(
    project_uuid: UUID, ref_id: Any = ..., iter_id: int = ...
) -> None:
    """
    Get Project Iteration Results
    """
    pass
