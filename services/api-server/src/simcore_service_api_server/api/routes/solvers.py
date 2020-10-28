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
    KeyIdentifier,
    RunInput,
    RunOutput,
    RunProxy,
    RunState,
    Solver,
    SolverKey,
    SolverOutput,
    SolverOverview,
)
from ...modules.catalog import CatalogApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.services import get_api_client

# from fastapi.responses import RedirectResponse
logger = logging.getLogger(__name__)

router = APIRouter()


## SOLVERS ------------


@router.get("", response_model=List[SolverOverview])
async def list_solvers(
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Lists an overview of all solvers. Each solver overview includes all released versions """
    # TODO: pagination
    # TODO: deduce user
    user_id = 1

    available_services = await catalog_client.get(
        "/services",
        params={"user_id": user_id, "details": False},
        headers={"x-simcore-products-name": "osparc"},
    )

    # TODO: move this sorting down to database?
    # Create list list of the latest version of each solver
    latest_solvers: Dict[SolverOverview] = {}
    for service in available_services:
        if service.get("type") == "computational":
            service_key = service["key"]
            solver = latest_solvers.get(service_key)

            if not solver or packaging.version.parse(
                solver.latest_version
            ) < packaging.version.parse(service["version"]):
                try:
                    latest_solvers[service_key] = SolverOverview(
                        solver_key=service_key,
                        title=service["name"],
                        maintainer=service["contact"],
                        latest_version=service["version"],
                        solver_url=url_for(
                            "get_solver_released_by_version",
                            solver_key=pathname2url(service_key),
                            version=service["version"],
                        ),
                    )
                except ValidationError as err:
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

    return sorted(latest_solvers.values(), key=attrgetter("solver_key"))


@router.get("/{solver_key:path}", response_model=Solver)
async def get_solver(solver_key: SolverKey):
    """ Returs a description of the solver and all its releases """
    raise NotImplementedError()


@router.get("/{solver_key:path}/{version}", response_model=Solver)
async def get_solver_released_by_version(
    solver_key: SolverKey, version: str = LATEST_VERSION
):
    # FIXME: router ccannto distinguish this from get_solver!!

    # url = app.url_path_for("get_solver_released")
    # response = RedirectResponse(url=url)
    # return response
    solver_id = compose_solver_id(solver_key, version)
    return await get_solver_released(solver_id)


@router.get("/{solver_id}", response_model=Solver)
async def get_solver_released(solver_id: UUID):
    raise NotImplementedError()


## RUNS ---------------
@router.get("/{solver_id}/jobs")
async def list_jobs(solver_id: UUID):
    """ List of all jobs (could be finished) by user of a given solver """
    # TODO: add pagination
    # similar to ps = process status
    raise NotImplementedError()


@router.post("/{solver_id}/jobs", response_model=RunProxy)
async def create_job(solver_id: UUID, inputs: Optional[List[RunInput]] = None):
    """ Runs a solver with given inputs """

    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of job based on solver_id and inputs
    return RunProxy()


@router.get("/{solver_id}/jobs/{job_id}", response_model=RunProxy)
async def get_job(solver_id: UUID, job_id: UUID):
    raise NotImplementedError()


@router.post("/{solver_id}/jobs/{job_id}:start", response_model=RunProxy)
async def start_job(solver_id: UUID, job_id: UUID):
    raise NotImplementedError()


@router.post("/{solver_id}/jobs/{job_id}:run", response_model=RunProxy)
async def run_job(solver_id: UUID, inputs: Optional[List[RunInput]] = None):
    """ create + start job in a single call """
    raise NotImplementedError()


@router.post("/{solver_id}/jobs/{job_id}:stop", response_model=RunProxy)
async def stop_job(solver_id: UUID, job_id: UUID):
    raise NotImplementedError()


@router.post("/{solver_id}/jobs/{job_id}:inspect", response_model=RunState)
async def inspect_job(solver_id: UUID):
    raise NotImplementedError()


@router.get("/{solver_id}/jobs/{job_id}/outputs", response_model=List[RunOutput])
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
def compose_solver_id(solver_key: SolverKey, version: str) -> UUID:
    return uuidlib.uuid3(NAMESPACE_SOLVER_KEY, f"{solver_key}:{version}")
