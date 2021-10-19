# pylint: disable=unused-argument

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


class Solver(BaseModel):
    """A released solver with a specific version"""


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


@router.get("", response_model=List[Solver])
def list_solvers():
    """Lists all available solvers (latest version)"""


@router.get("/releases", response_model=List[Solver], summary="Lists All Releases")
def list_solvers_releases():
    """Lists all released solvers (all released versions)"""


@router.get(
    "/{solver_key:path}/latest",
    response_model=Solver,
    summary="Get Latest Release of a Solver",
)
def get_solver(
    solver_key: SolverKeyId,
):
    """Gets latest release of a solver"""


@router.get("/{solver_key:path}/releases", response_model=List[Solver])
def list_solver_releases(
    solver_key: SolverKeyId,
):
    """Lists all releases of a given solver"""


@router.get("/{solver_key:path}/releases/{version}", response_model=Solver)
def get_solver_release(
    solver_key: SolverKeyId,
    version: VersionStr,
):
    """Gets a specific release of a solver"""


@router.get(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=List[Job],
)
def list_jobs(
    solver_key: SolverKeyId,
    version: str,
):
    ...


@router.post(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=Job,
)
def create_job(
    solver_key: SolverKeyId,
    version: str,
    inputs: JobInputs,
):
    ...


@router.get("/{solver_key:path}/releases/{version}/jobs/{job_id}", response_model=Job)
def get_job(
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
def start_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    ...


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:stop", response_model=Job
)
def stop_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    ...


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:inspect",
    response_model=JobStatus,
)
def inspect_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    ...


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}/outputs",
    response_model=JobOutputs,
)
def get_job_outputs(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
):
    ...
