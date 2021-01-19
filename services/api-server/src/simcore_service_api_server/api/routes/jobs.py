import logging
from contextlib import contextmanager
from typing import Callable, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from ...models.schemas.solvers import Job, JobInput, JobOutput, JobState, KeyIdentifier
from ..dependencies.application import get_reverse_url_mapper
from .jobs_faker import the_fake_impl
from .solvers import router as solvers_router

logger = logging.getLogger(__name__)


router = APIRouter()


## JOBS ---------------
#
# - Similar to docker container's API design (container = job and image = solver)
#


@solvers_router.get("/{solver_id}/jobs/")
async def list_jobs(
    solver_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs with a given solver """
    # TODO: add pagination
    # similar to ps = process status
    return [
        Job(
            solver_url=url_for(
                "get_solver_by_id",
                solver_id=job["solver_id"],
            ),
            inspect_url=url_for("inspect_job", job_id=job["job_id"]),
            outputs_url=url_for("list_job_outputs", job_id=job["job_id"]),
            **job,
        )
        for job in the_fake_impl.iter_jobs(solver_id)
    ]


# pylint: disable=dangerous-default-value
@solvers_router.post("/{solver_id}/jobs/", response_model=Job)
async def create_job(
    solver_id: UUID,
    inputs: List[JobInput] = [],
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Creates a job for a solver with given inputs.

    NOTE: This operation does **not** start the job
    """

    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of job based on solver_id and inputs

    job = the_fake_impl.create_job(solver_id, inputs)

    return Job(
        solver_url=url_for(
            "get_solver_by_id",
            solver_id=job["solver_id"],
        ),
        inspect_url=url_for("inspect_job", job_id=job["job_id"]),
        outputs_url=url_for("list_job_outputs", job_id=job["job_id"]),
        **job,
    )


@solvers_router.post("/{solver_id}/jobs:run", response_model=JobState)
async def run_job(
    solver_id: UUID,
    inputs: List[JobInput] = [],
):
    """ create + start job in a single call """
    job = the_fake_impl.create_job(solver_id, inputs)
    job_state = the_fake_impl.start_job(job["job_id"])
    return job_state


@router.get("")
async def list_all_jobs(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs created by user """
    # TODO: add pagination and filtering (e.g. all active jobs etc)
    # similar docker ps -a
    return [
        Job(
            solver_url=url_for(
                "get_solver_by_id",
                solver_id=job["solver_id"],
            ),
            inspect_url=url_for("inspect_job", job_id=job["job_id"]),
            outputs_url=url_for("list_job_outputs", job_id=job["job_id"]),
            **job,
        )
        for job in the_fake_impl.iter_jobs()
    ]


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    with errors_mapper():

        job = the_fake_impl.job_info[job_id]
        return Job(
            solver_url=url_for(
                "get_solver_by_id",
                solver_id=job["solver_id"],
            ),
            inspect_url=url_for("inspect_job", job_id=job["job_id"]),
            outputs_url=url_for("list_job_outputs", job_id=job["job_id"]),
            **job,
        )


@router.post("/{job_id}:start", response_model=JobState)
async def start_job(job_id: UUID):
    with errors_mapper():
        job_state = the_fake_impl.start_job(job_id)
        return job_state


@router.post("/{job_id}:stop", response_model=Job)
async def stop_job(
    job_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    with errors_mapper():
        job = the_fake_impl.stop_job(job_id)
        return Job(
            solver_url=url_for(
                "get_solver_by_id",
                solver_id=job["solver_id"],
            ),
            inspect_url=url_for("inspect_job", job_id=job["job_id"]),
            outputs_url=url_for("list_job_outputs", job_id=job["job_id"]),
            **job,
        )


@router.post("/{job_id}:inspect", response_model=JobState)
async def inspect_job(job_id: UUID):
    with errors_mapper():
        state = the_fake_impl.job_states[job_id]
        return state


@router.get("/{job_id}/outputs", response_model=List[JobOutput])
async def list_job_outputs(job_id: UUID):
    with errors_mapper():
        outputs = the_fake_impl.job_outputs[job_id]
        return outputs


@router.get("/{job_id}/outputs/{output_name}", response_model=JobOutput)
async def get_job_output(job_id: UUID, output_name: KeyIdentifier):
    with errors_mapper((KeyError, StopIteration)):
        outputs = the_fake_impl.job_outputs[job_id]
        return next(output for output in outputs if output.name == output_name)


# HELPERS ------------


@contextmanager
def errors_mapper(to_not_found=KeyError):
    try:
        yield
    except to_not_found as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from err
