import functools
import logging
import uuid as uuidlib
from operator import attrgetter
from typing import Callable, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from starlette import status

from ...models.schemas.solvers import (
    LATEST_VERSION,
    Job,
    JobInput,
    JobOutput,
    JobState,
    KeyIdentifier,
    Solver,
    SolverImageName,
    SolverOutput,
)
from ...modules.catalog import CatalogApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.services import get_api_client
from .solvers_fake import FAKE

logger = logging.getLogger(__name__)

router = APIRouter()


## JOBS ---------------


@router.get("/{solver_id}/jobs")
async def list_jobs(solver_id: UUID):
    """ List of all jobs (could be finished) by user of a given solver """
    # TODO: add pagination
    # similar to ps = process status
    raise NotImplementedError()


@router.post("/{solver_id}/jobs", response_model=Job)
async def create_job(solver_id: UUID, inputs: Optional[List[JobInput]] = None):
    """ Jobs a solver with given inputs """

    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of job based on solver_id and inputs
    return Job()


@router.get("/{solver_id}/jobs/{job_id}", response_model=Job)
async def get_job(solver_id: UUID, job_id: UUID):
    raise NotImplementedError()


@router.post("/{solver_id}/jobs/{job_id}:start", response_model=Job)
async def start_job(solver_id: UUID, job_id: UUID):
    raise NotImplementedError()


@router.post("/{solver_id}/jobs/{job_id}:run", response_model=Job)
async def run_job(solver_id: UUID, inputs: Optional[List[JobInput]] = None):
    """ create + start job in a single call """
    raise NotImplementedError()


@router.post("/{solver_id}/jobs/{job_id}:stop", response_model=Job)
async def stop_job(solver_id: UUID, job_id: UUID):
    raise NotImplementedError()


@router.post("/{solver_id}/jobs/{job_id}:inspect", response_model=JobState)
async def inspect_job(solver_id: UUID):
    raise NotImplementedError()


@router.get("/{solver_id}/jobs/{job_id}/outputs", response_model=List[JobOutput])
async def list_job_outputs(solver_id: UUID, job_id: UUID):
    raise NotImplementedError()


@router.get(
    "/{solver_id}/jobs/{job_id}/outputs/{output_key}", response_model=SolverOutput
)
async def get_job_output(solver_id: UUID, job_id: UUID, output_key: KeyIdentifier):
    raise NotImplementedError()


# HELPERS ----

NAMESPACE_SOLVER_KEY = uuidlib.UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")


@functools.lru_cache()
def compose_solver_id(solver_key: SolverImageName, version: str) -> UUID:
    # FIXME: this is a temporary solution. Should be image id

    return uuidlib.uuid3(NAMESPACE_SOLVER_KEY, f"{solver_key}:{version}")
