from typing import List
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, constr

#
# TODO: model details missing
# TODO: auth missing
#

# MODELS -----------------------------------------------------------------------------------------

COMPUTATIONAL_SERVICE_KEY_RE = r"^(simcore)/(services)/comp(/[\w/-]+)+$"

SolverKeyId = constr(
    strip_whitespace=True,
    regex=COMPUTATIONAL_SERVICE_KEY_RE,
)

VersionStr = constr(strip_whitespace=True)


class Job(BaseModel):
    ...


class JobStatus(BaseModel):
    ...


class JobInputs(BaseModel):
    ...


class JobOutputs(BaseModel):
    ...


# ROUTES -----------------------------------------------------------------------------------------

router = APIRouter()


@router.get(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=List[Job],
)
async def list_jobs(
    solver_key: SolverKeyId,
    version: str,
):
    ...


@router.post(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=Job,
)
async def create_job(
    solver_key: SolverKeyId,
    version: str,
    inputs: JobInputs,
):
    ...


@router.get("/{solver_key:path}/releases/{version}/jobs/{job_id}", response_model=Job)
async def get_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    """Gets job of a given solver"""
    ...


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:start",
    response_model=JobStatus,
)
async def start_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    ...


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:stop", response_model=Job
)
async def stop_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    ...


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:inspect",
    response_model=JobStatus,
)
async def inspect_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    ...


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}/outputs",
    response_model=JobOutputs,
)
async def get_job_outputs(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    ...
