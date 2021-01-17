import functools
import hashlib
import logging
import uuid as uuidlib
from datetime import datetime
from typing import Callable, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from ...models.schemas.solvers import Job, JobInput, JobOutput, JobState, KeyIdentifier
from ..dependencies.application import get_reverse_url_mapper
from .jobs_faker import FAKE
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
        for job in FAKE.user_jobs
        if job["solver_id"] == str(solver_id)
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
    sha = hashlib.sha256(
        " ".join(input.json() for input in inputs).encode("utf-8")
    ).hexdigest()

    # TODO: check if job exists already?? Do not consider date??
    job_id = compose_job_id(solver_id, sha, datetime.utcnow())

    job = dict(
        job_id=str(job_id),
        inputs_sha=sha,
        solver_id=str(solver_id),
    )
    FAKE.user_jobs.append(job)

    return Job(
        solver_url=url_for(
            "get_solver_by_id",
            solver_id=job["solver_id"],
        ),
        inspect_url=url_for("inspect_job", job_id=job["job_id"]),
        outputs_url=url_for("list_job_outputs", job_id=job["job_id"]),
        **job,
    )


@router.get("")
async def list_all_jobs(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs created by user """
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
        for job in FAKE.user_jobs
    ]


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    try:
        found = next(
            Job(
                solver_url=url_for(
                    "get_solver_by_id",
                    solver_id=job["solver_id"],
                ),
                inspect_url=url_for("inspect_job", job_id=job["job_id"]),
                outputs_url=url_for("list_job_outputs", job_id=job["job_id"]),
                **job,
            )
            for job in FAKE.user_jobs
            if job["job_id"] == str(job_id)
        )
    except StopIteration as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from err
    else:
        return found


@router.post("/{job_id}:start", response_model=JobState)
async def start_job(job_id: UUID):
    raise NotImplementedError()


@router.post("/{job_id}:run", response_model=Job)
async def run_job(inputs: Optional[List[JobInput]] = None):
    """ create + start job in a single call """
    raise NotImplementedError()


@router.post("/{job_id}:stop", response_model=Job)
async def stop_job(job_id: UUID):
    raise NotImplementedError()


@router.post("/{job_id}:inspect", response_model=JobState)
async def inspect_job(solver_id: UUID):
    raise NotImplementedError()


@router.get("/{job_id}/outputs", response_model=List[JobOutput])
async def list_job_outputs(job_id: UUID):
    raise NotImplementedError()


@router.get("/{job_id}/outputs/{output_key}", response_model=JobOutput)
async def get_job_output(job_id: UUID, output_key: KeyIdentifier):
    raise NotImplementedError()


# HELPERS ----

NAMESPACE_JOB_KEY = uuidlib.UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")


@functools.lru_cache()
def compose_job_id(solver_id: UUID, inputs_sha: str, created_at: str) -> UUID:
    # FIXME: this is a temporary solution. Should be image id

    return uuidlib.uuid3(NAMESPACE_JOB_KEY, f"{solver_id}:{inputs_sha}:{created_at}")
