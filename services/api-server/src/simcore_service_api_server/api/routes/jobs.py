import logging
from typing import Callable, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from ...models.schemas.jobs import Job, JobInput, JobOutput, JobStatus
from ...models.schemas.solvers import SolverKeyId, VersionStr
from ..dependencies.application import get_reverse_url_mapper
from .jobs_faker import the_fake_impl

logger = logging.getLogger(__name__)


router = APIRouter()


## JOBS ---------------
#
# - Similar to docker container's API design (container = job and image = solver)
#
# - TODO: solvers_router.post("/{solver_id}/jobs:run", response_model=JobStatus) disabled since MAG is not convinced it is necessary for now
#


async def list_jobs_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    url_for: Callable,
):
    solver_resource_name = f"solvers/{solver_key}/releases/{version}"
    return [
        job.copy(
            update={
                "url": url_for("get_job", job_id=job.id),
                "solver_url": url_for(
                    "get_solver_release", solver_key=solver_key, version=version
                ),
                "outputs_url": url_for("list_job_outputs", job_id=job.id),
            }
        )
        for job in the_fake_impl.job_values(solver_resource_name)
    ]


async def create_job_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    inputs: List[JobInput],
    url_for: Callable,
):
    """Creates a job for a solver with given inputs.

    NOTE: This operation does **not** start the job
    """
    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of job based on solver_id and inputs

    job = the_fake_impl.create_job(f"{solver_key}:{version}", inputs)
    return job.copy(
        update={
            "url": url_for("get_job", job_id=job.id),
            "solver_url": url_for(
                "get_solver_release", solver_key=solver_key, version=version
            ),
            "outputs_url": url_for("list_job_outputs", job_id=job.id),
        }
    )


@router.get("", response_model=List[Job])
async def list_all_jobs(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs created by user """
    return [
        job.copy(
            update={
                "url": url_for("get_job", job_id=job.id),
                "solver_url": url_for(
                    "get_solver_release",
                    solver_key=job.solver_key,
                    version=job.solver_version,
                ),
                "outputs_url": url_for("list_job_outputs", job_id=job.id),
            }
        )
        for job in the_fake_impl.job_values()
    ]


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    try:
        job = the_fake_impl.jobs[job_id]
        return job.copy(
            update={
                "url": url_for("get_job", job_id=job.id),
                "solver_url": url_for(
                    "get_solver_release",
                    solver_key=job.solver_key,
                    version=job.solver_version,
                ),
                "outputs_url": url_for("list_job_outputs", job_id=job.id),
            }
        )

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job {job_id} does not exists"
        ) from err


@router.post("/{job_id}:start", response_model=JobStatus)
async def start_job(job_id: UUID):
    try:
        job_state = the_fake_impl.start_job(job_id)
        return job_state

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job {job_id} does not exists"
        ) from err


@router.post("/{job_id}:stop", response_model=Job)
async def stop_job(
    job_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    try:
        job = the_fake_impl.stop_job(job_id)
        return job.copy(
            update={
                "url": url_for("get_job", job_id=job.id),
                "solver_url": url_for(
                    "get_solver_release",
                    solver_key=job.solver_key,
                    version=job.solver_version,
                ),
                "outputs_url": url_for("list_job_outputs", job_id=job.id),
            }
        )

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job {job_id} does not exists"
        ) from err


@router.post("/{job_id}:inspect", response_model=JobStatus)
async def inspect_job(job_id: UUID):
    try:
        state = the_fake_impl.job_status[job_id]
        return state

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job {job_id} does not exists"
        ) from err


@router.get("/{job_id}/outputs", response_model=List[JobOutput])
async def list_job_outputs(job_id: UUID):
    try:
        outputs = the_fake_impl.job_outputs[job_id]
        return outputs

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No outputs found in job '{job_id}'",
        ) from err


@router.get("/{job_id}/outputs/{output_name}", response_model=JobOutput)
async def get_job_output(job_id: UUID, output_name: str):
    try:
        outputs = the_fake_impl.job_outputs[job_id]
        return next(output for output in outputs if output.name == output_name)

    except (KeyError, StopIteration) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No output '{output_name}' was not found in job {job_id}",
        ) from err
