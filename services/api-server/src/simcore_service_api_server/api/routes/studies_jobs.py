import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from models_library.api_schemas_webserver.projects import ProjectUpdate
from models_library.api_schemas_webserver.projects_nodes import NodeOutputs
from models_library.clusters import ClusterID
from models_library.function_services_catalog.services import file_picker
from models_library.projects_nodes import InputID, InputTypes
from pydantic import PositiveInt
from servicelib.logging_utils import log_context

from ...api.dependencies.authentication import get_current_user_id
from ...api.dependencies.services import get_api_client
from ...api.dependencies.webserver import get_webserver_session
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.jobs import (
    Job,
    JobID,
    JobInputs,
    JobMetadata,
    JobMetadataUpdate,
    JobOutputs,
    JobStatus,
)
from ...models.schemas.studies import Study, StudyID
from ...services.director_v2 import DirectorV2Api
from ...services.solver_job_models_converters import create_jobstatus_from_task
from ...services.storage import StorageApi
from ...services.study_job_models_converters import (
    create_job_from_study,
    create_job_outputs_from_project_outputs,
    get_project_and_file_inputs_from_job_inputs,
)
from ...services.webserver import AuthSession
from ._common import API_SERVER_DEV_FEATURES_ENABLED
from ._jobs import start_project, stop_project

_logger = logging.getLogger(__name__)
router = APIRouter()


#
# - Study maps to project
# - study-job maps to run??
#


def _compose_job_resource_name(study_key, job_id) -> str:
    """Creates a unique resource name for solver's jobs"""
    return Job.compose_resource_name(
        parent_name=Study.compose_resource_name(study_key),
        job_id=job_id,
    )


@router.get(
    "/{study_id:uuid}/jobs",
    response_model=Page[Job],
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def list_study_jobs(
    study_id: StudyID,
    page_params: Annotated[PaginationParams, Depends()],
):
    msg = f"list study jobs study_id={study_id!r} with pagination={page_params!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.post(
    "/{study_id:uuid}/jobs",
    response_model=Job,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def create_study_job(
    study_id: StudyID,
    job_inputs: JobInputs,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
) -> Job:
    project = await webserver_api.clone_project(project_id=study_id, hidden=True)
    job = create_job_from_study(
        study_key=study_id, project=project, job_inputs=job_inputs
    )
    project = await webserver_api.update_project(
        project_id=job.id, update_params=ProjectUpdate(name=job.name)
    )

    project_inputs = await webserver_api.get_project_inputs(project_id=project.uuid)

    file_param_nodes = {}
    for node_id, node in project.workbench.items():
        if (
            node.key == file_picker.META.key
            and node.outputs is not None
            and len(node.outputs) == 0
        ):
            file_param_nodes[node.label] = node_id

    file_inputs: dict[InputID, InputTypes] = {}

    (
        new_project_inputs,
        new_project_file_inputs,
    ) = get_project_and_file_inputs_from_job_inputs(
        project_inputs, file_inputs, job_inputs
    )

    for node_label, file_link in new_project_file_inputs.items():
        node_id = file_param_nodes[node_label]

        await webserver_api.update_node_outputs(
            project.uuid, node_id, NodeOutputs(outputs={"outFile": file_link})
        )

    if len(new_project_inputs) > 0:
        await webserver_api.update_project_inputs(project.uuid, new_project_inputs)

    assert job.name == _compose_job_resource_name(study_id, job.id)

    return job


@router.get(
    "/{study_id:uuid}/jobs/{job_id:uuid}",
    response_model=Job,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def get_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    msg = f"get study job study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.delete(
    "/{study_id:uuid}/jobs/{job_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorGet}},
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def delete_study_job(
    study_id: StudyID,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    """Deletes an existing study job"""
    job_name = _compose_job_resource_name(study_id, job_id)
    with log_context(_logger, logging.DEBUG, f"Deleting Job '{job_name}'"):
        await webserver_api.delete_project(project_id=job_id)


@router.post(
    "/{study_id:uuid}/jobs/{job_id:uuid}:start",
    response_model=JobStatus,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def start_study_job(
    request: Request,
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    cluster_id: ClusterID | None = None,
) -> JobStatus:
    job_name = _compose_job_resource_name(study_id, job_id)
    with log_context(_logger, logging.DEBUG, f"Starting Job '{job_name}'"):
        await start_project(
            request=request,
            job_id=job_id,
            expected_job_name=job_name,
            webserver_api=webserver_api,
            cluster_id=cluster_id,
        )
        job_status: JobStatus = await inspect_study_job(
            study_id=study_id,
            job_id=job_id,
            user_id=user_id,
            director2_api=director2_api,
        )
        return job_status


@router.post(
    "/{study_id:uuid}/jobs/{job_id:uuid}:stop",
    response_model=JobStatus,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def stop_study_job(
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
):
    job_name = _compose_job_resource_name(study_id, job_id)
    with log_context(_logger, logging.DEBUG, f"Stopping Job '{job_name}'"):
        return await stop_project(
            job_id=job_id, user_id=user_id, director2_api=director2_api
        )


@router.post(
    "/{study_id}/jobs/{job_id}:inspect",
    response_model=JobStatus,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def inspect_study_job(
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
) -> JobStatus:
    job_name = _compose_job_resource_name(study_id, job_id)
    _logger.debug("Inspecting Job '%s'", job_name)

    task = await director2_api.get_computation(job_id, user_id)
    job_status: JobStatus = create_jobstatus_from_task(task)
    return job_status


@router.post(
    "/{study_id}/jobs/{job_id}/outputs",
    response_model=JobOutputs,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_study_job_outputs(
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
):
    job_name = _compose_job_resource_name(study_id, job_id)
    _logger.debug("Getting Job Outputs for '%s'", job_name)

    project_outputs = await webserver_api.get_project_outputs(job_id)
    job_outputs: JobOutputs = await create_job_outputs_from_project_outputs(
        job_id, project_outputs, user_id, storage_client
    )

    return job_outputs


@router.post(
    "/{study_id}/jobs/{job_id}/outputs/logfile",
    response_class=RedirectResponse,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def get_study_job_output_logfile(study_id: StudyID, job_id: JobID):
    msg = f"get study job output logfile study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.get(
    "/{study_id}/jobs/{job_id}/metadata",
    response_model=JobMetadata,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def get_study_job_custom_metadata(
    study_id: StudyID,
    job_id: JobID,
):
    """Gets custom metadata from a job"""
    msg = f"Gets metadata attached to study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4313"
    raise NotImplementedError(msg)


@router.put(
    "/{study_id}/jobs/{job_id}/metadata",
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def replace_study_job_custom_metadata(
    study_id: StudyID, job_id: JobID, replace: JobMetadataUpdate
):
    """Changes job's custom metadata"""
    msg = f"Attaches metadata={replace.metadata!r} to study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4313"
    raise NotImplementedError(msg)
