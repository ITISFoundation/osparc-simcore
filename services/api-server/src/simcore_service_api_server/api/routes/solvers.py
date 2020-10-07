import functools
import uuid as uuidlib
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter

# from fastapi.responses import RedirectResponse

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

router = APIRouter()



## SOLVERS ------------

@router.get("", response_model=List[SolverOverview])
async def list_solvers():
    """ Lists an overview of all solvers. Each solver overview includes all released versions """
    # pagination
    pass


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


@router.get("/{solver_id}/runs/{run_id}", response_model=RunProxy)
async def get_run(solver_id: UUID, run_id: UUID):
    pass


@router.get("/{solver_id}/runs/{run_id}/state", response_model=RunState)
async def inspect_run_state(solver_id: UUID):
    pass


@router.get("/{solver_id}/runs/{run_id}:stop", response_model=RunProxy)
async def stop_run(solver_id: UUID, run_id: UUID):
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
