import logging
from operator import attrgetter
from typing import Callable, List

from fastapi import APIRouter, Depends, HTTPException, status
from httpx import HTTPStatusError
from pydantic import ValidationError
from pydantic.errors import PydanticValueError

from ...models.schemas.solvers import Solver, SolverKeyId, VersionStr
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
# - TODO: allow release_tags instead of versions in the next iteration.
#    Would be nice to have /solvers/foo/releases/latest or solvers/foo/releases/3 , similar to docker tagging


@router.get("", response_model=List[Solver])
async def list_solvers(
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Lists all available solvers (latest version) """
    solvers: List[Solver] = await catalog_client.list_latest_releases(user_id)

    for solver in solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(solvers, key=attrgetter("id"))


@router.get("/releases", response_model=List[Solver])
async def list_solvers_releases(
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Lists all released solvers (all released versions) """
    assert await catalog_client.is_responsive()  # nosec

    solvers: List[Solver] = await catalog_client.list_solvers(user_id)

    for solver in solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(solvers, key=attrgetter("id", "pep404_version"))


@router.get("/{solver_key}", response_model=Solver)
async def get_solver(
    solver_key: SolverKeyId,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
) -> Solver:
    """ Gets latest release of a solver """
    try:

        solver = await catalog_client.get_latest_release(user_id, solver_key)
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )
        assert solver.id == solver_key  # nosec

        return solver

    except (KeyError, HTTPStatusError) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver with id={solver_key} not found",
        ) from err


@router.get("/{solver_key}/jobs", response_model=List[Job])
async def list_jobs(
    solver_key: SolverKeyId,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs on a given solver """
    solver = await catalog_client.get_latest_release(user_id, solver_key)
    return await list_jobs_impl(solver.id, solver.version, url_for)


# pylint: disable=dangerous-default-value
@router.post("/{solver_key}/jobs", response_model=Job)
async def create_job(
    solver_key: SolverKeyId,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    inputs: List[JobInput] = [],
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Creates a job on a solver with given inputs.

    NOTE: This operation does **not** start the job
    """
    solver = await catalog_client.get_latest_release(user_id, solver_key)
    return await create_job_impl(solver.id, solver.version, inputs, url_for)


@router.get("/{solver_key}/releases/{version}", response_model=Solver)
async def get_solver_release(
    solver_key: SolverKeyId,
    version: VersionStr,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
) -> Solver:
    """ Gets a specific release of a solver """
    try:
        solver = await catalog_client.get_solver(user_id, solver_key, version)

        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

        return solver

    except (
        ValueError,
        IndexError,
        ValidationError,
        HTTPStatusError,
        PydanticValueError,
    ) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver {solver_key}:{version} not found",
        ) from err


@router.get("/{solver_key}/releases/{version}/jobs", response_model=List[Job])
async def list_jobs_in_release(
    solver_key: SolverKeyId,
    version: str,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs in a specific released solver """
    solver = await catalog_client.get_solver(user_id, solver_key, version)
    return await list_jobs_impl(solver.id, solver.version, url_for)


# pylint: disable=dangerous-default-value
@router.post("/{solver_key}/releases/{version}/jobs", response_model=Job)
async def create_job_in_release(
    solver_key: SolverKeyId,
    version: str,
    inputs: List[JobInput] = [],
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Creates a job in a specific release with given inputs.

    NOTE: This operation does **not** start the job
    """
    solver = await catalog_client.get_solver(user_id, solver_key, version)
    return await create_job_impl(solver.id, solver.version, inputs, url_for)
