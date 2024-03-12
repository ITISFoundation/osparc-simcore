import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from simcore_service_api_server.api.dependencies.webserver import get_webserver_session
from simcore_service_api_server.api.errors.http_error import create_error_json_response
from simcore_service_api_server.services.webserver import AuthSession
from simcore_service_storage.exceptions import ProjectNotFoundError

from ...models.pagination import Page, PaginationParams
from ...models.schemas.jobs import (
    Job,
    JobID,
    JobInputs,
    JobMetadata,
    JobMetadataUpdate,
    JobOutputs,
    JobStatus,
)
from ...models.schemas.studies import StudyID
from ...services.study_job_models_converters import (
    create_job_from_study,
    get_project_and_file_inputs_from_job_inputs,
)
from ._common import API_SERVER_DEV_FEATURES_ENABLED

_logger = logging.getLogger(__name__)
router = APIRouter()


#
# - Study maps to project
# - study-job maps to run??
#


def _compose_job_resource_name(study_key, job_id) -> str:
    """Creates a unique resource name for solver's jobs"""
    return Job.compose_resource_name(
        parent_name=Study.compose_resource_name(study_key),  # type: ignore
        job_id=job_id,
    )


@router.get(
    "/{study_id:uuid}/jobs",
    response_model=Page[Job],
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
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
):
    try:
        project = await webserver_api.clone_project(project_id=study_id)

        project_inputs = await webserver_api.get_project_inputs(project_id=project.uuid)

        file_param_nodes = {}
        for node_id, node in project.workbench.items():
            assert node.outputs is not None  # no sec
            if (
                node.key == "simcore/services/frontend/file-picker"
                and len(node.outputs) == 0
            ):
                file_param_nodes[node.label] = node_id

        file_inputs = {}

        (
            new_project_inputs,
            new_project_file_inputs,
        ) = get_project_and_file_inputs_from_job_inputs(
            project_inputs, file_inputs, job_inputs
        )

        for node_label, file_link in new_project_file_inputs.items():
            node_id = file_param_nodes[node_label]

            await webserver_api.update_node_outputs(
                project.uuid, node_id, {"outputs": {"outFile": file_link}}
            )

        if len(new_project_inputs) > 0:
            await webserver_api.update_project_inputs(project.uuid, new_project_inputs)

        job = create_job_from_study(
            study_key=study_id, project=project, job_inputs=job_inputs
        )

        assert job.name == _compose_job_resource_name(study_id, job.id)

        return job

    except ProjectNotFoundError:
        return create_error_json_response(
            f"Cannot find study={study_id!r}.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


@router.get(
    "/{study_id:uuid}/jobs/{job_id:uuid}",
    response_model=Job,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
)
async def get_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    msg = f"get study job study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.delete(
    "/{study_id:uuid}/jobs/{job_id:uuid}",
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
)
async def delete_study_job(study_id: StudyID, job_id: JobID):
    msg = f"delete study job study_id={study_id!r} job_id={job_id!r}.  SEE https://github.com/ITISFoundation/osparc-simcore/issues/4111"
    raise NotImplementedError(msg)


@router.post(
    "/{study_id:uuid}/jobs/{job_id:uuid}:start",
    response_model=JobStatus,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
)
async def start_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    msg = f"start study job study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.post(
    "/{study_id:uuid}/jobs/{job_id:uuid}:stop",
    response_model=Job,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
)
async def stop_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    msg = f"stop study job study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.post(
    "/{study_id}/jobs/{job_id}:inspect",
    response_model=JobStatus,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
)
async def inspect_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    msg = f"inspect study job study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.post(
    "/{study_id}/jobs/{job_id}/outputs",
    response_model=JobOutputs,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
)
async def get_study_job_outputs(
    study_id: StudyID,
    job_id: JobID,
):
    msg = f"get study job outputs study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.post(
    "/{study_id}/jobs/{job_id}/outputs/logfile",
    response_class=RedirectResponse,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
)
async def get_study_job_output_logfile(study_id: StudyID, job_id: JobID):
    msg = f"get study job output logfile study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.get(
    "/{study_id}/jobs/{job_id}/metadata",
    response_model=JobMetadata,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_description="Not implemented",
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
    response_description="Not implemented",
)
async def replace_study_job_custom_metadata(
    study_id: StudyID, job_id: JobID, replace: JobMetadataUpdate
):
    """Changes job's custom metadata"""
    msg = f"Attaches metadata={replace.metadata!r} to study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4313"
    raise NotImplementedError(msg)
