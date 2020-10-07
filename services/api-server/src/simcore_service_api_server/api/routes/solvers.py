from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter

from ...models.schemas.solvers import RunProxy, RunState, SolverInput, LATEST_VERSION, SolverOverview, SolverDetailed

router = APIRouter()


@router.get("", response_model=List[SolverOverview])
async def list_solvers():
    # pagination
    pass


@router.get("/{solver_id}", response_model=SolverDetailed)
async def get_solver(solver_id: UUID):
    pass

@router.get("/{solver_id}/{version}", response_model=SolverDetailed)
async def get_solver_given_version(solver_id: UUID, version: str=LATEST_VERSION):
    pass



@router.get("/{solver_id}:run", response_model=RunProxy)
async def start_solver(solver_id: UUID, inputs: Optional[ List[SolverInput] ] = []):
    """ Starts latest version of the solver with given inputs """

    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of run based on solver_id and inputs

    return RunProxy()


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
