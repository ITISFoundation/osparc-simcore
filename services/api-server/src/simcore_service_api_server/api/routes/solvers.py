import functools
import logging
import uuid as uuidlib
from operator import attrgetter
from typing import Callable, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from packing import version
from pydantic import ValidationError

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
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.services import CatalogApi, get_catalog_api_client

# from fastapi.responses import RedirectResponse
logger = logging.getLogger(__name__)

router = APIRouter()


## SOLVERS ------------


@router.get("", response_model=List[SolverOverview])
async def list_solvers(
    catalog_client: CatalogApi = Depends(get_catalog_api_client),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Lists an overview of all solvers. Each solver overview includes all released versions """
    # TODO: pagination
    # TODO: deduce user
    user_id = 0

    resp = await catalog_client.get(
        "/services",
        params={"user_id": user_id, "details": False},
        headers={"x-simcore-products-name": "osparc"},
    )

    # TODO: move this sorting down to database?
    # Create list list of the latest version of each solver
    latest_solvers: Dict[SolverOverview] = {}
    for service in resp.json():
        if service.get("type") == "computational":
            service_key = service["key"]
            solver = latest_solvers.get(service_key)

            if not solver or version.parse(solver.latest_version) < version.parse(
                service["version"]
            ):
                try:
                    latest_solvers[service_key] = SolverOverview(
                        solver_key=service_key,
                        title=service["name"],
                        maintainer=service["authors"][0]["email"],
                        latest_version=service["version"],
                        solver_url=url_for(
                            "get_solver_released_by_version",
                            solver_key=service_key,
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
                    logger.error("API catalog response changed?")
                    # raise internal error?

    return sorted(latest_solvers.values(), key=attrgetter("solver_key"))


@router.get("/{solver_key:path}", response_model=Solver)
async def get_solver(solver_key: SolverKey):
    """ Returs a description of the solver and all its releases """
    pass


@router.get("/{solver_key:path}/{version}", response_model=Solver)
async def get_solver_released_by_version(
    solver_key: SolverKey, version: str = LATEST_VERSION
):
    # url = app.url_path_for("get_solver_released")
    # response = RedirectResponse(url=url)
    # return response

    solver_id = compose_solver_id(solver_key, version)
    return await get_solver_released(solver_id)


@router.get("/{solver_id}", response_model=Solver)
async def get_solver_released(solver_id: UUID):
    pass


## RUNS ---------------


@router.post("/{solver_id}/runs", response_model=RunProxy)
async def create_solver_run(solver_id: UUID, inputs: Optional[List[RunInput]] = None):
    """ Runs a solver with given inputs """

    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of run based on solver_id and inputs

    return RunProxy()


@router.get("/{solver_id}/runs")
async def list_runs(solver_id: UUID):
    """ List of all runs (could be finished) by user of a given solver """
    # TODO: add pagination
    # similar to ps = process status
    pass


@router.get("/{solver_id}/runs/{run_id}:stop", response_model=RunProxy)
async def stop_run(solver_id: UUID, run_id: UUID):
    pass


@router.get("/{solver_id}/runs/{run_id}", response_model=RunProxy)
async def get_run(solver_id: UUID, run_id: UUID):
    pass


@router.get("/{solver_id}/runs/{run_id}:inspect", response_model=RunState)
async def inspect_run(solver_id: UUID):
    pass


@router.get("/{solver_id}/runs/{run_id}/outputs", response_model=List[RunOutput])
async def list_run_outputs(solver_id: UUID, run_id: UUID):
    pass


@router.get(
    "/{solver_id}/runs/{run_id}/outputs/{output_key}", response_model=SolverOutput
)
async def get_run_output(solver_id: UUID, run_id: UUID, output_key: KeyIdentifier):
    pass


# HELPERS ----

NAMESPACE_SOLVER_KEY = uuidlib.UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")


@functools.lru_cache()
def compose_solver_id(solver_key: SolverKey, version: str) -> UUID:
    return uuidlib.uuid3(NAMESPACE_SOLVER_KEY, f"{solver_key}:{version}")
