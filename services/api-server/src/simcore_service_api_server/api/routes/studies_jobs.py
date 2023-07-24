import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse

from ...models.pagination import Page, PaginationParams
from ...models.schemas.jobs import (
    Job,
    JobID,
    JobMetadata,
    JobMetadataUpdate,
    JobOutputs,
    JobStatus,
)
from ...models.schemas.studies import StudyID
from ._common import API_SERVER_DEV_FEATURES_ENABLED, job_output_logfile_responses

_logger = logging.getLogger(__name__)
router = APIRouter()


#
# - Study maps to project
# - study-job maps to run??
#


@router.get(
    "/{study_id:uuid}/jobs",
    response_model=Page[Job],
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
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
async def create_study_job(study_id: StudyID):
    msg = f"create study job study_id={study_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.get(
    "/{study_id:uuid}/jobs/{job_id:uuid}",
    response_model=Job,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
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
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def delete_study_job(study_id: StudyID, job_id: JobID):
    msg = f"delete study job study_id={study_id!r} job_id={job_id!r}.  SEE https://github.com/ITISFoundation/osparc-simcore/issues/4111"
    raise NotImplementedError(msg)


@router.post(
    "/{study_id:uuid}/jobs/{job_id:uuid}:start",
    response_model=JobStatus,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
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
    responses=job_output_logfile_responses,
)
async def get_study_job_output_logfile(study_id: StudyID, job_id: JobID):
    msg = f"get study job output logfile study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.get(
    "/{study_id}/jobs/{job_id}/metadata",
    response_model=JobMetadata,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
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
)
async def replace_study_job_custom_metadata(
    study_id: StudyID, job_id: JobID, replace: JobMetadataUpdate
):
    """Changes job's custom metadata"""
    msg = f"Attaches metadata={replace.metadata!r} to study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4313"
    raise NotImplementedError(msg)
