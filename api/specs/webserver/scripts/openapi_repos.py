

from typing import Union

from fastapi import APIRouter, FastAPI, Header
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.meta_modeling._rest_handlers import

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "repository",
    ],
)



@router.get(
    '/repos/projects',
    response_model=ReposProjectsGetResponse,
    responses={'422': {'model': ReposProjectsGetResponse1}},

)
def simcore_service_webserver_version_control_handlers__list_repos_handler(
    offset: Optional[int] = 0, limit: Optional[conint(ge=1, le=50)] = 20
) -> Union[ReposProjectsGetResponse, ReposProjectsGetResponse1]:
    """
    List Repos
    """
    pass


@router.get(
    '/repos/projects/{project_uuid}/checkpoints',
    response_model=ReposProjectsProjectUuidCheckpointsGetResponse,
    responses={'422': {'model': ReposProjectsProjectUuidCheckpointsGetResponse1}},

)
def simcore_service_webserver_version_control_handlers__list_checkpoints_handler(
    project_uuid: UUID,
    offset: Optional[int] = 0,
    limit: Optional[conint(ge=1, le=50)] = 20,
) -> Union[
    ReposProjectsProjectUuidCheckpointsGetResponse,
    ReposProjectsProjectUuidCheckpointsGetResponse1,
]:
    """
    List Checkpoints
    """
    pass


@router.post(
    '/repos/projects/{project_uuid}/checkpoints',
    response_model=None,
    responses={
        '201': {'model': ReposProjectsProjectUuidCheckpointsPostResponse},
        '422': {'model': ReposProjectsProjectUuidCheckpointsPostResponse1},
    },

)
def simcore_service_webserver_version_control_handlers__create_checkpoint_handler(
    project_uuid: UUID, body: ReposProjectsProjectUuidCheckpointsPostRequest = ...
) -> Union[
    None,
    ReposProjectsProjectUuidCheckpointsPostResponse,
    ReposProjectsProjectUuidCheckpointsPostResponse1,
]:
    """
    Create Checkpoint
    """
    pass


@router.get(
    '/repos/projects/{project_uuid}/checkpoints/HEAD',
    response_model=ReposProjectsProjectUuidCheckpointsHEADGetResponse,
    responses={'422': {'model': ReposProjectsProjectUuidCheckpointsHEADGetResponse1}},

)
def simcore_service_webserver_version_control_handlers__get_checkpoint_handler_head(
    project_uuid: UUID,
) -> Union[
    ReposProjectsProjectUuidCheckpointsHEADGetResponse,
    ReposProjectsProjectUuidCheckpointsHEADGetResponse1,
]:
    """
    Gets HEAD (i.e. current) checkpoint
    """
    pass


@router.get(
    '/repos/projects/{project_uuid}/checkpoints/{ref_id}',
    response_model=ReposProjectsProjectUuidCheckpointsRefIdGetResponse,
    responses={'422': {'model': ReposProjectsProjectUuidCheckpointsRefIdGetResponse1}},

)
def simcore_service_webserver_version_control_handlers__get_checkpoint_handler(
    ref_id: Any, project_uuid: UUID = ...
) -> Union[
    ReposProjectsProjectUuidCheckpointsRefIdGetResponse,
    ReposProjectsProjectUuidCheckpointsRefIdGetResponse1,
]:
    """
    Get Checkpoint
    """
    pass


@router.patch(
    '/repos/projects/{project_uuid}/checkpoints/{ref_id}',
    response_model=ReposProjectsProjectUuidCheckpointsRefIdPatchResponse,
    responses={
        '422': {'model': ReposProjectsProjectUuidCheckpointsRefIdPatchResponse1}
    },

)
def simcore_service_webserver_version_control_handlers__update_checkpoint_annotations_handler(
    ref_id: Any,
    project_uuid: UUID = ...,
    body: ReposProjectsProjectUuidCheckpointsRefIdPatchRequest = ...,
) -> Union[
    ReposProjectsProjectUuidCheckpointsRefIdPatchResponse,
    ReposProjectsProjectUuidCheckpointsRefIdPatchResponse1,
]:
    """
    Update Checkpoint Annotations
    """
    pass


@router.get(
    '/repos/projects/{project_uuid}/checkpoints/{ref_id}/workbench/view',
    response_model=ReposProjectsProjectUuidCheckpointsRefIdWorkbenchViewGetResponse,
    responses={
        '422': {
            'model': ReposProjectsProjectUuidCheckpointsRefIdWorkbenchViewGetResponse1
        }
    },

)
def simcore_service_webserver_version_control_handlers__view_project_workbench_handler(
    ref_id: Any, project_uuid: UUID = ...
) -> Union[
    ReposProjectsProjectUuidCheckpointsRefIdWorkbenchViewGetResponse,
    ReposProjectsProjectUuidCheckpointsRefIdWorkbenchViewGetResponse1,
]:
    """
    View Project Workbench
    """
    pass


@router.post(
    '/repos/projects/{project_uuid}/checkpoints/{ref_id}:checkout',
    response_model=ReposProjectsProjectUuidCheckpointsRefIdCheckoutPostResponse,
    responses={
        '422': {'model': ReposProjectsProjectUuidCheckpointsRefIdCheckoutPostResponse1}
    },

)
def simcore_service_webserver_version_control_handlers__checkout_handler(
    ref_id: Any, project_uuid: UUID = ...
) -> Union[
    ReposProjectsProjectUuidCheckpointsRefIdCheckoutPostResponse,
    ReposProjectsProjectUuidCheckpointsRefIdCheckoutPostResponse1,
]:
    """
    Checkout
    """
    pass
