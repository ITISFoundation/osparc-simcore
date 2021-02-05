import logging
from operator import attrgetter
from typing import Callable, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from httpx import HTTPStatusError
from pydantic import ValidationError

from ...models.schemas.solvers import (
    LATEST_VERSION,
    Solver,
    SolverName,
    compose_solver_id,
)
from ...modules.catalog import CatalogApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_api_client
from .jobs import Job, JobInput, create_job_impl, list_jobs_impl

logger = logging.getLogger(__name__)

router = APIRouter()


## SOLVERS -----------------------------------------------------------------------------------------
#
# - TODO: pagination, result ordering, filter field and results fields?? SEE https://cloud.google.com/apis/design/standard_methods#list
# - TODO: :search? SEE https://cloud.google.com/apis/design/custom_methods#common_custom_methods
# - TODO: move more of this logic to catalog service
# - TODO: error handling!!!


@router.get("", response_model=List[Solver])
async def list_solvers(
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    assert await catalog_client.is_responsive()  # nosec

    solvers: List[Solver] = await catalog_client.list_solvers(user_id)

    for solver in solvers:
        solver.url = url_for(
            "get_solver",
            solver_id=solver.id,
        )

        # updates id -> (name, version)
        catalog_client.ids_cache_map[solver.id] = (solver.name, solver.version)

    return sorted(solvers, key=attrgetter("name", "pep404_version"))


@router.get("/{solver_id}", response_model=Solver)
async def get_solver(
    solver_id: UUID,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
) -> Solver:
    try:
        if solver_id in catalog_client.ids_cache_map:
            solver_name, solver_version = catalog_client.ids_cache_map[solver_id]

            solver = await get_solver_by_name_and_version(
                solver_name, solver_version, user_id, catalog_client, url_for
            )

        else:

            def _with_id(s: Solver):
                return compose_solver_id(s.name, s.version) == solver_id

            solvers: List[Solver] = await catalog_client.list_solvers(user_id, _with_id)
            assert len(solvers) <= 1  # nosec
            solver = solvers[0]

        solver.url = url_for(
            "get_solver",
            solver_id=solver.id,
        )
        assert solver.id == solver_id  # nosec

        # updates id -> (name, version)
        catalog_client.ids_cache_map[solver.id] = (solver.name, solver.version)

        return solver

    except (KeyError, HTTPStatusError) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver with id={solver_id} not found",
        ) from err


@router.get("/{solver_id}/jobs", response_model=List[Job])
async def list_jobs(
    solver_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs with a given solver """
    return await list_jobs_impl(solver_id, url_for)


# pylint: disable=dangerous-default-value
@router.post("/{solver_id}/jobs", response_model=Job)
async def create_job(
    solver_id: UUID,
    inputs: List[JobInput] = [],
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Creates a job for a solver with given inputs.

    NOTE: This operation does **not** start the job
    """
    return await create_job_impl(solver_id, inputs, url_for)


@router.get("/{solver_name:path}/{version}", response_model=Solver)
async def get_solver_by_name_and_version(
    solver_name: SolverName,
    version: str,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
) -> Solver:
    try:
        if version == LATEST_VERSION:
            solver = await catalog_client.get_latest_solver(user_id, solver_name)
        else:
            solver = await catalog_client.get_solver(user_id, solver_name, version)

        solver.url = url_for(
            "get_solver",
            solver_id=solver.id,
        )

        # updates id -> (name, version)
        catalog_client.ids_cache_map[solver.id] = (solver.name, solver.version)
        return solver

    except (ValueError, IndexError, ValidationError, HTTPStatusError) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver {solver_name}:{version} not found",
        ) from err
