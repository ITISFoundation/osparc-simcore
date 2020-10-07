import functools
import uuid as uuidlib
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter

from ...models.schemas.solvers import (
    LATEST_VERSION,
    RunProxy,
    RunState,
    SolverDetailed,
    SolverInput,
    SolverKey,
    SolverOverview,
)

router = APIRouter()


## SOLVERS ------------


@router.get("", response_model=List[SolverOverview])
async def list_solvers():
    """ Lists an overview of all solvers. Each solver overview includes all released versions """
    # pagination
    pass


@router.get("/{solver_key:path}", response_model=SolverDetailed)
async def get_solver(solver_key: SolverKey):
    """ Returs a description of the solver and all its releases """
    pass


@router.get("/{solver_key:path}/{version}", response_model=SolverDetailed)
async def get_solver_released_by_version(
    solver_key: SolverKey, version: str = LATEST_VERSION
):
    solver_id = compose_solver_id(solver_key, version)
    return await get_solver_released(solver_id)


@router.get("/{solver_id}", response_model=SolverDetailed)
async def get_solver_released(solver_id: UUID):
    pass


@router.get("/{solver_id}:run", response_model=RunProxy)
async def start_solver(solver_id: UUID, inputs: Optional[List[SolverInput]] = []):
    """ Starts latest version of the solver with given inputs """

    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of run based on solver_id and inputs

    return RunProxy()


## RUNS ---------------


@router.get("/{solver_id}/runs")
async def list_solver_runs(solver_id: UUID):
    """ List of all runs (could be finished) by user of a given solver """
    # TODO: add pagination
    # similar to ps = process status
    pass


@router.get("/{solver_id}/runs/{run_id}", response_model=RunProxy)
async def get_solver_run(solver_id: UUID, run_id: UUID):
    pass


@router.get("/{solver_id}/runs/{run_id}/state", response_model=RunState)
async def get_solver_run_state(solver_id: UUID):
    pass


@router.get("/{solver_id}/runs/{run_id}:stop", response_model=RunProxy)
async def stop_solver_run(solver_id: UUID, run_id: UUID):
    pass


# HELPERS ----


@functools.lru_cache()
def compose_solver_id(solver_key: str, version: str) -> UUID:
    return uuidlib.uuid3(uuidlib.NAMESPACE_URL, f"{solver_key}:{version}")
