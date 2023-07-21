

from typing import Union

from fastapi import APIRouter, FastAPI, Header
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects.models import ProjectType


router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
    ],
)





@router.get('/projects', response_model=ProjectsGetResponse,)
def list_projects(
    limit: Optional[conint(ge=1, lt=50)] = 20,
    offset: Optional[conint(ge=0)] = 0,
    type: Optional[Type1] = 'all',
    show_hidden: Optional[bool] = False,
) -> ProjectsGetResponse:
    """
    List Projects
    """
    pass


@router.post(
    '/projects',
    response_model=None,
    responses={'201': {'model': ProjectsPostResponse}},

)
def create_project(
    from_study: Optional[UUID] = None,
    as_template: Optional[bool] = False,
    copy_data: Optional[bool] = True,
    hidden: Optional[bool] = False,
    body: Any,
) -> Union[None, ProjectsPostResponse]:
    """
    Creates a new project or copies an existing one
    """
    pass


@router.get('/projects/active', response_model=ProjectsActiveGetResponse, tags=['project'])
def get_active_project(client_session_id: str) -> ProjectsActiveGetResponse:
    """
    Get Active Project
    """
    pass


@router.get(
    '/projects/{project_id}',
    response_model=ProjectsProjectIdGetResponse,

)
def get_project(project_id: UUID) -> ProjectsProjectIdGetResponse:
    """
    Get Project
    """
    pass


@router.put(
    '/projects/{project_id}',
    response_model=ProjectsProjectIdPutResponse,

)
def replace_project(
    project_id: UUID, body: ProjectsProjectIdPutRequest = ...
) -> ProjectsProjectIdPutResponse:
    """
    Replace Project
    """
    pass


@router.delete('/projects/{project_id}', response_model=None, tags=['project'])
def delete_project(project_id: UUID) -> None:
    """
    Delete Project
    """
    pass


@router.patch(
    '/projects/{project_id}',
    response_model=ProjectsProjectIdPatchResponse,

)
def update_project(
    project_id: UUID, body: ProjectsProjectIdPatchRequest = ...
) -> ProjectsProjectIdPatchResponse:
    """
    Update Project
    """
    pass


@router.get(
    '/projects/{project_id}/inputs',
    response_model=ProjectsProjectIdInputsGetResponse,

)
def get_project_inputs(project_id: UUID) -> ProjectsProjectIdInputsGetResponse:
    """
    Get Project Inputs
    """
    pass


@router.patch(
    '/projects/{project_id}/inputs',
    response_model=ProjectsProjectIdInputsPatchResponse,

)
def update_project_inputs(
    project_id: UUID, body: List[ProjectsProjectIdInputsPatchRequest] = ...
) -> ProjectsProjectIdInputsPatchResponse:
    """
    Update Project Inputs
    """
    pass


@router.get(
    '/projects/{project_id}/metadata/ports',
    response_model=ProjectsProjectIdMetadataPortsGetResponse,

)
def list_project_metadata_ports(
    project_id: UUID,
) -> ProjectsProjectIdMetadataPortsGetResponse:
    """
    List Project Metadata Ports
    """
    pass


@router.post(
    '/projects/{project_id}/nodes',
    response_model=None,
    responses={
        '201': {'model': ProjectsProjectIdNodesPostResponse},
        'default': {'model': ProjectsProjectIdNodesPostResponse1},
    },

)
def create_node(
    project_id: str, body: ProjectsProjectIdNodesPostRequest = ...
) -> Union[
    None, ProjectsProjectIdNodesPostResponse, ProjectsProjectIdNodesPostResponse1
]:
    """
    Create a new node
    """
    pass


@router.get(
    '/projects/{project_id}/nodes/{node_id}',
    response_model=ProjectsProjectIdNodesNodeIdGetResponse,
    responses={'default': {'model': ProjectsProjectIdNodesNodeIdGetResponse1}},

)
def get_node(
    project_id: str, node_id: str = ...
) -> Union[
    ProjectsProjectIdNodesNodeIdGetResponse, ProjectsProjectIdNodesNodeIdGetResponse1
]:
    pass


@router.delete(
    '/projects/{project_id}/nodes/{node_id}',
    response_model=None,
    responses={'default': {'model': ProjectsProjectIdNodesNodeIdDeleteResponse}},

)
def delete_node(
    project_id: str, node_id: str = ...
) -> Union[None, ProjectsProjectIdNodesNodeIdDeleteResponse]:
    pass


@router.get(
    '/projects/{project_id}/nodes/{node_id}/resources',
    response_model=ProjectsProjectIdNodesNodeIdResourcesGetResponse,
    responses={'default': {'model': ProjectsProjectIdNodesNodeIdResourcesGetResponse1}},

)
def get_node_resources(
    project_id: str, node_id: str = ...
) -> Union[
    ProjectsProjectIdNodesNodeIdResourcesGetResponse,
    ProjectsProjectIdNodesNodeIdResourcesGetResponse1,
]:
    pass


@router.put(
    '/projects/{project_id}/nodes/{node_id}/resources',
    response_model=ProjectsProjectIdNodesNodeIdResourcesPutResponse,
    responses={'default': {'model': ProjectsProjectIdNodesNodeIdResourcesPutResponse1}},

)
def replace_node_resources(
    project_id: str,
    node_id: str = ...,
    body: ProjectsProjectIdNodesNodeIdResourcesPutRequest = ...,
) -> Union[
    ProjectsProjectIdNodesNodeIdResourcesPutResponse,
    ProjectsProjectIdNodesNodeIdResourcesPutResponse1,
]:
    pass


@router.post(
    '/projects/{project_id}/nodes/{node_id}:restart',
    response_model=None,
    responses={'default': {'model': ProjectsProjectIdNodesNodeIdRestartPostResponse}},

)
def restart_node(
    project_id: str, node_id: str = ...
) -> Union[None, ProjectsProjectIdNodesNodeIdRestartPostResponse]:
    pass


@router.post(
    '/projects/{project_id}/nodes/{node_id}:retrieve',
    response_model=ProjectsProjectIdNodesNodeIdRetrievePostResponse,
    responses={'default': {'model': ProjectsProjectIdNodesNodeIdRetrievePostResponse1}},

)
def retrieve_node(
    project_id: str,
    node_id: str = ...,
    body: ProjectsProjectIdNodesNodeIdRetrievePostRequest = ...,
) -> Union[
    ProjectsProjectIdNodesNodeIdRetrievePostResponse,
    ProjectsProjectIdNodesNodeIdRetrievePostResponse1,
]:
    pass


@router.post(
    '/projects/{project_id}/nodes/{node_id}:start',
    response_model=None,
    responses={'default': {'model': ProjectsProjectIdNodesNodeIdStartPostResponse}},

)
def start_node(
    project_id: str, node_id: str = ...
) -> Union[None, ProjectsProjectIdNodesNodeIdStartPostResponse]:
    pass


@router.post(
    '/projects/{project_id}/nodes/{node_id}:stop',
    response_model=None,
    responses={'default': {'model': ProjectsProjectIdNodesNodeIdStopPostResponse}},

)
def stop_node(
    project_id: str, node_id: str = ...
) -> Union[None, ProjectsProjectIdNodesNodeIdStopPostResponse]:
    pass


@router.get(
    '/projects/{project_id}/outputs',
    response_model=ProjectsProjectIdOutputsGetResponse,

)
def get_project_outputs(project_id: UUID) -> ProjectsProjectIdOutputsGetResponse:
    """
    Get Project Outputs
    """
    pass


@router.get(
    '/projects/{project_id}/state',
    response_model=ProjectsProjectIdStateGetResponse,
    responses={'default': {'model': ProjectsProjectIdStateGetResponse1}},

)
def get_project_state(
    project_id: str,
) -> Union[ProjectsProjectIdStateGetResponse, ProjectsProjectIdStateGetResponse1]:
    """
    returns the state of a project
    """
    pass


@router.post(
    '/projects/{project_id}:close',
    response_model=None,
    responses={'default': {'model': ProjectsProjectIdClosePostResponse}},

)
def close_project(
    project_id: str, body: str = ...
) -> Union[None, ProjectsProjectIdClosePostResponse]:
    """
    Closes a given project
    """
    pass


@router.post(
    '/projects/{project_id}:duplicate',
    response_model=ProjectsProjectIdDuplicatePostResponse,
    responses={'default': {'model': ProjectsProjectIdDuplicatePostResponse1}},
    tags=['exporter'],
)
def duplicate_project(
    project_id: str,
) -> Union[
    ProjectsProjectIdDuplicatePostResponse, ProjectsProjectIdDuplicatePostResponse1
]:
    """
    duplicates an existing project
    """
    pass


@router.post(
    '/projects/{project_id}:open',
    response_model=ProjectsProjectIdOpenPostResponse,
    responses={'default': {'model': ProjectsProjectIdOpenPostResponse1}},

)
def open_project(
    project_id: str, body: str = ...
) -> Union[ProjectsProjectIdOpenPostResponse, ProjectsProjectIdOpenPostResponse1]:
    """
    Open a given project
    """
    pass


@router.post(
    '/projects/{project_id}:xport',
    response_model=bytes,
    responses={'default': {'model': ProjectsProjectIdXportPostResponse}},
    tags=['exporter'],
)
def export_project(project_id: str) -> Union[bytes, ProjectsProjectIdXportPostResponse]:
    """
    creates an archive of the project and downloads it
    """
    pass


@router.get(
    '/projects/{project_uuid}/checkpoint/{ref_id}/iterations',
    response_model=ProjectsProjectUuidCheckpointRefIdIterationsGetResponse,
    responses={
        '422': {'model': ProjectsProjectUuidCheckpointRefIdIterationsGetResponse1}
    },
    tags=['meta-projects'],
)
def simcore_service_webserver_meta_modeling_handlers__list_meta_project_iterations_handler(
    project_uuid: UUID,
    ref_id: Any = ...,
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=50)] = 20,
) -> Union[
    ProjectsProjectUuidCheckpointRefIdIterationsGetResponse,
    ProjectsProjectUuidCheckpointRefIdIterationsGetResponse1,
]:
    """
    List Project Iterations
    """
    pass


@router.get(
    '/projects/{project_uuid}/checkpoint/{ref_id}/iterations/-/results',
    response_model=ProjectsProjectUuidCheckpointRefIdIterationsResultsGetResponse,
    responses={
        '422': {
            'model': ProjectsProjectUuidCheckpointRefIdIterationsResultsGetResponse1
        }
    },
    tags=['meta-projects'],
)
def simcore_service_webserver_meta_modeling_handlers__list_meta_project_iterations_results_handler(
    project_uuid: UUID,
    ref_id: Any = ...,
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=50)] = 20,
) -> Union[
    ProjectsProjectUuidCheckpointRefIdIterationsResultsGetResponse,
    ProjectsProjectUuidCheckpointRefIdIterationsResultsGetResponse1,
]:
    """
    List Project Iterations Results
    """
    pass


@router.get(
    '/projects/{project_uuid}/checkpoint/{ref_id}/iterations/{iter_id}',
    response_model=None,
    tags=['meta-projects'],
)
def simcore_service_webserver_meta_modeling_handlers__get_meta_project_iterations_handler(
    project_uuid: UUID, ref_id: Any = ..., iter_id: int = ...
) -> None:
    """
    Get Project Iterations
    """
    pass


@router.get(
    '/projects/{project_uuid}/checkpoint/{ref_id}/iterations/{iter_id}/results',
    response_model=None,
    tags=['meta-projects'],
)
def simcore_service_webserver_meta_modeling_handlers__get_meta_project_iteration_results_handler(
    project_uuid: UUID, ref_id: Any = ..., iter_id: int = ...
) -> None:
    """
    Get Project Iteration Results
    """
    pass


@router.put(
    '/projects/{study_uuid}/tags/{tag_id}',
    response_model=ProjectsStudyUuidTagsTagIdPutResponse,
    responses={'default': {'model': ProjectsStudyUuidTagsTagIdPutResponse1}},

)
def add_tag(
    tag_id: int, study_uuid: str = ...
) -> Union[
    ProjectsStudyUuidTagsTagIdPutResponse, ProjectsStudyUuidTagsTagIdPutResponse1
]:
    """
    Links an existing label with an existing study
    """
    pass


@router.delete(
    '/projects/{study_uuid}/tags/{tag_id}',
    response_model=ProjectsStudyUuidTagsTagIdDeleteResponse,
    responses={'default': {'model': ProjectsStudyUuidTagsTagIdDeleteResponse1}},

)
def remove_tag(
    tag_id: int, study_uuid: str = ...
) -> Union[
    ProjectsStudyUuidTagsTagIdDeleteResponse, ProjectsStudyUuidTagsTagIdDeleteResponse1
]:
    """
    Removes an existing link between a label and a study
    """
    pass


@router.post(
    '/projects:import',
    response_model=ProjectsImportPostResponse,
    responses={'default': {'model': ProjectsImportPostResponse1}},
    tags=['exporter'],
)
def import_project() -> Union[ProjectsImportPostResponse, ProjectsImportPostResponse1]:
    """
    Create new project from an archive
    """
    pass
