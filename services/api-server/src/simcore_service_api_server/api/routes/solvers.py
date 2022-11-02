import logging
from operator import attrgetter
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from httpx import HTTPStatusError
from pydantic import ValidationError
from pydantic.errors import PydanticValueError
from servicelib.error_codes import create_error_code

from ...core.settings import ApplicationSettings, BasicSettings
from ...models.schemas.solvers import Solver, SolverKeyId, SolverPort, VersionStr
from ...modules.catalog import CatalogApi
from ..dependencies.application import get_reverse_url_mapper, get_settings
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_api_client

logger = logging.getLogger(__name__)

router = APIRouter()
settings = BasicSettings.create_from_envs()

## SOLVERS -----------------------------------------------------------------------------------------
#
# - TODO: pagination, result ordering, filter field and results fields?? SEE https://cloud.google.com/apis/design/standard_methods#list
# - TODO: :search? SEE https://cloud.google.com/apis/design/custom_methods#common_custom_methods
# - TODO: move more of this logic to catalog service
# - TODO: error handling!!!
# - TODO: allow release_tags instead of versions in the next iteration.
#    Would be nice to have /solvers/foo/releases/latest or solvers/foo/releases/3 , similar to docker tagging


@router.get("", response_model=list[Solver])
async def list_solvers(
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
    app_settings: ApplicationSettings = Depends(get_settings),
):
    """Lists all available solvers (latest version)"""
    solvers: list[Solver] = await catalog_client.list_latest_releases(
        user_id, product_name=app_settings.API_SERVER_DEFAULT_PRODUCT_NAME
    )

    for solver in solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(solvers, key=attrgetter("id"))


@router.get("/releases", response_model=list[Solver], summary="Lists All Releases")
async def list_solvers_releases(
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
    app_settings: ApplicationSettings = Depends(get_settings),
):
    """Lists all released solvers (all released versions)"""
    assert await catalog_client.is_responsive()  # nosec

    solvers: list[Solver] = await catalog_client.list_solvers(
        user_id, product_name=app_settings.API_SERVER_DEFAULT_PRODUCT_NAME
    )

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
    app_settings: ApplicationSettings = Depends(get_settings),
) -> Solver:
    """Gets latest release of a solver"""
    # IMPORTANT: by adding /latest, we avoid changing the order of this entry in the router list
    # otherwise, {solver_key:path} will override and consume any of the paths that follow.
    try:

        solver = await catalog_client.get_latest_release(
            user_id,
            solver_key,
            product_name=app_settings.API_SERVER_DEFAULT_PRODUCT_NAME,
        )
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


@router.get("/{solver_key:path}/releases", response_model=list[Solver])
async def list_solver_releases(
    solver_key: SolverKeyId,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
    app_settings: ApplicationSettings = Depends(get_settings),
):
    """Lists all releases of a given solver"""
    releases: list[Solver] = await catalog_client.list_solver_releases(
        user_id, solver_key, product_name=app_settings.API_SERVER_DEFAULT_PRODUCT_NAME
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
    app_settings: ApplicationSettings = Depends(get_settings),
) -> Solver:
    """Gets a specific release of a solver"""
    try:
        solver = await catalog_client.get_solver(
            user_id,
            solver_key,
            version,
            product_name=app_settings.API_SERVER_DEFAULT_PRODUCT_NAME,
        )

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


@router.get(
    "/{solver_key:path}/releases/{version}/ports",
    response_model=list[SolverPort],
    include_in_schema=settings.API_SERVER_DEV_FEATURES_ENABLED,
)
async def list_solver_ports(
    solver_key: SolverKeyId,
    version: VersionStr,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    app_settings: ApplicationSettings = Depends(get_settings),
):
    """Lists inputs and outputs of a given solver

    New in *version 0.5.0* (only with API_SERVER_DEV_FEATURES_ENABLED=1)
    """
    try:

        ports = await catalog_client.get_solver_ports(
            user_id,
            solver_key,
            version,
            product_name=app_settings.API_SERVER_DEFAULT_PRODUCT_NAME,
        )
        return ports

    except ValidationError as err:
        error_code = create_error_code(err)
        logger.exception(
            "Corrupted port data for service %s [%s]",
            f"{solver_key}:{version}",
            f"{error_code}",
            extra={"error_code": error_code},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Port definition of {solver_key}:{version} seems corrupted [{error_code}]",
        ) from err

    except HTTPStatusError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ports for solver {solver_key}:{version} not found",
        ) from err
