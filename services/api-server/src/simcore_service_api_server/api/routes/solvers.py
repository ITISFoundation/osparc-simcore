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
    """Lists all available solvers (latest version)"""
    solvers: List[Solver] = await catalog_client.list_latest_releases(user_id)

    for solver in solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(solvers, key=attrgetter("id"))


@router.get("/releases", response_model=List[Solver], summary="Lists All Releases")
async def list_solvers_releases(
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Lists all released solvers (all released versions)"""
    assert await catalog_client.is_responsive()  # nosec

    solvers: List[Solver] = await catalog_client.list_solvers(user_id)

    for solver in solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(solvers, key=attrgetter("id", "pep404_version"))


@router.get(
    "/{solver_key:path}/latest",
    response_model=Solver,
    summary="Get Latest Release of a Solver",
)
async def get_solver(
    solver_key: SolverKeyId,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
) -> Solver:
    """Gets latest release of a solver"""
    # IMPORTANT: by adding /latest, we avoid changing the order of this entry in the router list
    # otherwise, {solver_key:path} will override and consume any of the paths that follow.
    try:

        solver = await catalog_client.get_latest_release(user_id, solver_key)
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )
        assert solver.id == solver_key  # nosec

        return solver

    except (KeyError, HTTPStatusError, IndexError) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver with id={solver_key} not found",
        ) from err


@router.get("/{solver_key:path}/releases", response_model=List[Solver])
async def list_solver_releases(
    solver_key: SolverKeyId,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Lists all releases of a given solver"""
    releases: List[Solver] = await catalog_client.list_solver_releases(
        user_id, solver_key
    )

    for solver in releases:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(releases, key=attrgetter("pep404_version"))


@router.get("/{solver_key:path}/releases/{version}", response_model=Solver)
async def get_solver_release(
    solver_key: SolverKeyId,
    version: VersionStr,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
) -> Solver:
    """Gets a specific release of a solver"""
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
