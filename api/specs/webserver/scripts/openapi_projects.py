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


@router.post(
    "/projects/{project_id}:duplicate",
    response_model=ProjectsProjectIdDuplicatePostResponse,
    responses={"default": {"model": ProjectsProjectIdDuplicatePostResponse1}},
    tags=["exporter"],
)
def duplicate_project(
    project_id: str,
) -> ProjectsProjectIdDuplicatePostResponse | ProjectsProjectIdDuplicatePostResponse1:
    """
    duplicates an existing project
    """
    pass


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
    "/projects/{project_id}:xport",
    response_model=bytes,
    responses={"default": {"model": ProjectsProjectIdXportPostResponse}},
    tags=["exporter"],
)
def export_project(project_id: str) -> bytes | ProjectsProjectIdXportPostResponse:
    """
    creates an archive of the project and downloads it
    """
    pass


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


@router.post(
    "/projects:import",
    response_model=ProjectsImportPostResponse,
    responses={"default": {"model": ProjectsImportPostResponse1}},
    tags=["exporter"],
)
def import_project() -> ProjectsImportPostResponse | ProjectsImportPostResponse1:
    """
    Create new project from an archive
    """
    pass
