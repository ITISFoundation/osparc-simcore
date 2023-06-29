import logging
from typing import TypeAlias
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse

from ...models.schemas.jobs import Job, JobOutputs, JobStatus
from ...models.schemas.studies import StudyID
from ._common import API_SERVER_DEV_FEATURES_ENABLED, job_output_logfile_responses

_logger = logging.getLogger(__name__)
router = APIRouter()

#
# - Study maps to project
# - study-job maps to run??
#


JobID: TypeAlias = UUID


@router.get(
    "/studies/{study_id:uuid}/jobs",
    response_model=list[Job],
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def list_study_jobs(study_id: StudyID):
    raise NotImplementedError(
        f"list study jobs {study_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.post(
    "/studies/{study_id:uuid}/jobs",
    response_model=Job,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def create_study_job(study_id: StudyID):
    raise NotImplementedError(
        f"create study job {study_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.get(
    "/studies/{study_id:uuid}/jobs/{job_id:uuid}",
    response_model=Job,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    raise NotImplementedError(
        f"get study job {study_id=} {job_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.delete(
    "/studies/{study_id:uuid}/jobs/{job_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def delete_study_job(study_id: StudyID, job_id: JobID):
    raise NotImplementedError(
        f"delete study job {study_id=} {job_id=}.  SEE https://github.com/ITISFoundation/osparc-simcore/issues/4111"
    )


@router.post(
    "/studies/{study_id:uuid}/jobs/{job_id:uuid}:start",
    response_model=JobStatus,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def start_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    raise NotImplementedError(
        f"start study job {study_id=} {job_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.post(
    "/studies/{study_id:uuid}/jobs/{job_id:uuid}:stop",
    response_model=Job,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def stop_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    raise NotImplementedError(
        f"stop study job {study_id=} {job_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.post(
    "/studies/{study_id}/job/{job_id}:inspect",
    response_model=JobStatus,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def inspect_study_job(
    study_id: StudyID,
    job_id: JobID,
):
    raise NotImplementedError(
        f"inspect study job {study_id=} {job_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.post(
    "/studies/{study_id}/job/{job_id}/outputs",
    response_model=JobOutputs,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_study_job_outputs(
    study_id: StudyID,
    job_id: JobID,
):
    raise NotImplementedError(
        f"get study job outputs {study_id=} {job_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.post(
    "/studies/{study_id}/job/{job_id}/outputs/logfile",
    response_class=RedirectResponse,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    responses=job_output_logfile_responses,
)
async def get_study_job_output_logfile(study_id: StudyID, job_id: JobID):
    raise NotImplementedError(
        f"get study job output logfile {study_id=} {job_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )
