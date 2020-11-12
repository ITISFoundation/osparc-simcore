import functools
import logging
import uuid as uuidlib
from operator import attrgetter
from typing import Callable, Dict, List, Optional
from urllib.request import pathname2url
from uuid import UUID

import packaging.version
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
    SolverImage,
    SolverImageName,
    SolverOutput,
)
from ...modules.catalog import CatalogApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.services import get_api_client

# from fastapi.responses import RedirectResponse
logger = logging.getLogger(__name__)

router = APIRouter()


## SOLVERS ------------


@router.get("", response_model=List[Solver])
async def list_solvers(
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """
    Returns a list of the latest version of each solver
    """
    # TODO: pagination
    # TODO: deduce user
    # filter and format as in docker listings ??

    # FIXME: temporary hard-coded user!
    user_id = 1

    available_services = await catalog_client.get(
        "/services",
        params={"user_id": user_id, "details": False},
        headers={"x-simcore-products-name": "osparc"},
    )

    # TODO: move this sorting down to database?
    # Create list list of the latest version of each solver
    latest_solvers: Dict[str, Solver] = {}
    for service in available_services:
        if service["type"] == "computational":
            service_key = service["key"]

            solver = latest_solvers.get(service_key)

            if not solver or packaging.version.parse(
                solver.version
            ) < packaging.version.parse(service["version"]):
                try:
                    latest_solvers[service_key] = Solver(
                        # FIXME: image id is not provided
                        uid=compose_solver_id(service_key, service["version"]),
                        name=service_key,
                        title=service["name"],
                        maintainer=service["contact"],
                        version=service["version"],
                        description=service.get("description"),
                        solver_url=url_for(
                            "get_solver_by_name_and_version",
                            solver_name=pathname2url(service_key),
                            version=service["version"],
                        ),
                        # TODO: if field is not set in service, do not set here
                    )
                except ValidationError as err:
                    # NOTE: This is necessary because there are no guarantees
                    #       at the image registry. Therefore we exclude and warn
                    #       invalid items instead of returning error
                    logger.warning(
                        "Skipping invalid service returned by catalog '%s': %s",
                        service_key,
                        err,
                    )
                except (KeyError, IndexError) as err:
                    logger.error("API catalog response required fields did change!")
                    raise HTTPException(
                        status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Catalog API corrupted",
                    ) from err

    return sorted(latest_solvers.values(), key=attrgetter("name"))


@router.get("/{solver_name:path}/{version}", response_model=Solver)
async def get_solver_by_name_and_version(solver_name: SolverImageName, version: str):
    if version == LATEST_VERSION:
        return await get_solver_latest_version_by_name(solver_name)

    raise NotImplementedError(f"{solver_name}:{version}")


@router.get("/{solver_name:path}", response_model=Solver)
async def get_solver_latest_version_by_name(solver_name: SolverImageName):
    # catalog get / key:latest
    raise NotImplementedError(f"GET latest {solver_name}")


@router.get("/{solver_id}", response_model=Solver)
async def get_solver_by_id(solver_id: UUID):
    # catalog get /image_id
    raise NotImplementedError(f"GET solver {solver_id}")


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
