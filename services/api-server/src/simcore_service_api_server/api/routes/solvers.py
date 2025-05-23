import logging
from collections.abc import Callable
from operator import attrgetter
from typing import Annotated, Any

from common_library.pagination_tools import iter_pagination_params
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import create_page
from httpx import HTTPStatusError
from models_library.api_schemas_catalog.services import ServiceListFilters
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.services_enums import ServiceType
from pydantic import ValidationError

from ..._service_solvers import SolverService
from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.basic_types import VersionStr
from ...models.pagination import OnePage, Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.model_adapter import ServicePricingPlanGetLegacy
from ...models.schemas.solvers import Solver, SolverKeyId, SolverPort
from ...models.schemas.solvers_filters import SolversListFilters
from ...services_rpc.catalog import CatalogService
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.models_schemas_solvers_filters import get_solvers_filters
from ..dependencies.services import get_catalog_service, get_solver_service
from ..dependencies.webserver_http import AuthSession, get_webserver_session
from ._constants import (
    FMSG_CHANGELOG_ADDED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)

_logger = logging.getLogger(__name__)

_SOLVER_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Not found",
        "model": ErrorGet,
    },
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}

router = APIRouter(
    # /v0/solvers/
)


@router.get(
    "",
    response_model=list[Solver],
    responses=_SOLVER_STATUS_CODES,
    description=create_route_description(
        base="Lists all available solvers (latest version)",
        deprecated=True,
        alternative="GET /v0/solvers/page",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5"),
        ],
    ),
)
async def list_solvers(
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    services, _ = await catalog_service.list_latest_releases(
        filters=ServiceListFilters(service_type=ServiceType.COMPUTATIONAL),
    )
    solvers = [Solver.create_from_service(service=service) for service in services]

    for solver in solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(solvers, key=attrgetter("id"))


@router.get(
    "/page",
    response_model=Page[Solver],
    description=create_route_description(
        base="Lists all available solvers (paginated)",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.9-rc1"),
        ],
    ),
    include_in_schema=False,  # TO BE RELEASED in 0.9
)
async def list_all_solvers_paginated(
    page_params: Annotated[PaginationParams, Depends()],
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    filters: Annotated[SolversListFilters, Depends(get_solvers_filters)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    solvers, page_meta = await solver_service.list_all_solvers(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
        filter_by_solver_key_pattern=filters.solver_id,
        filter_by_version_display_pattern=filters.version_display,
    )

    for solver in solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    assert page_params.limit == page_meta.limit  # nosec
    assert page_params.offset == page_meta.offset  # nosec

    return create_page(
        solvers,
        total=page_meta.total,
        params=page_params,
    )


@router.get(
    "/releases",
    response_model=list[Solver],
    summary="Lists All Releases",
    responses=_SOLVER_STATUS_CODES,
    description=create_route_description(
        base="Lists **all** released solvers (not just latest version)",
        deprecated=True,
        alternative="GET /v0/solvers/{solver_key}/releases/page",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5"),
        ],
    ),
)
async def list_solvers_releases(
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):

    latest_solvers: list[Solver] = []
    for page_params in iter_pagination_params(limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE):
        solvers, page_meta = await solver_service.latest_solvers(
            pagination_offset=page_params.offset,
            pagination_limit=page_params.limit,
        )
        page_params.total_number_of_items = page_meta.total
        latest_solvers.extend(solvers)

    all_solvers = []
    for solver in latest_solvers:
        for page_params in iter_pagination_params(
            limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
        ):
            solvers, page_meta = await solver_service.solver_release_history(
                solver_key=solver.id,
                pagination_offset=page_params.offset,
                pagination_limit=page_params.limit,
            )
            page_params.total_number_of_items = page_meta.total
            all_solvers.extend(solvers)

    for solver in all_solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(all_solvers, key=attrgetter("id", "pep404_version"))


@router.get(
    "/{solver_key:path}/latest",
    response_model=Solver,
    responses=_SOLVER_STATUS_CODES,
    description=create_route_description(
        base="Gets latest release of a solver",
        changelog=[
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.7.1", "`version_display` field in the response"
            ),
        ],
    ),
)
async def get_solver(
    solver_key: SolverKeyId,
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    # IMPORTANT: by adding /latest, we avoid changing the order of this entry in the router list
    # otherwise, {solver_key:path} will override and consume any of the paths that follow.
    try:
        solver = await solver_service.get_latest_release(solver_key=solver_key)
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


@router.get(
    "/{solver_key:path}/releases",
    response_model=list[Solver],
    responses=_SOLVER_STATUS_CODES,
    description=create_route_description(
        base="Lists all releases of a given (one) solver",
        changelog=[
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.7.1", "`version_display` field in the response"
            ),
        ],
    ),
)
async def list_solver_releases(
    solver_key: SolverKeyId,
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    all_releases: list[Solver] = []
    for page_params in iter_pagination_params(limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE):
        solvers, page_meta = await solver_service.solver_release_history(
            solver_key=solver_key,
            pagination_offset=page_params.offset,
            pagination_limit=page_params.limit,
        )
        page_params.total_number_of_items = page_meta.total
        all_releases.extend(solvers)

    for solver in all_releases:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )

    return sorted(all_releases, key=attrgetter("pep404_version"))


@router.get(
    "/{solver_key:path}/releases/page",
    response_model=Page[Solver],
    description=create_route_description(
        base="Lists all releases of a give solver (paginated)",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.9-rc1"),
        ],
    ),
    include_in_schema=False,  # TO BE RELEASED in 0.9
)
async def list_solver_releases_paginated(
    solver_key: SolverKeyId,
    page_params: Annotated[PaginationParams, Depends()],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
):
    solvers, page_meta = await solver_service.solver_release_history(
        solver_key=solver_key,
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
    )

    for solver in solvers:
        solver.url = url_for(
            "get_solver_release", solver_key=solver.id, version=solver.version
        )
    page_params.limit = page_meta.limit
    page_params.offset = page_meta.offset
    return create_page(
        solvers,
        total=page_meta.total,
        params=page_params,
    )


@router.get(
    "/{solver_key:path}/releases/{version}",
    response_model=Solver,
    responses=_SOLVER_STATUS_CODES,
    description=create_route_description(
        base="Gets a specific release of a solver",
        changelog=[
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.7.1", "`version_display` field in the response"
            ),
        ],
    ),
)
async def get_solver_release(
    solver_key: SolverKeyId,
    version: VersionStr,
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    try:
        solver: Solver = await solver_service.get_solver(
            solver_key=solver_key,
            solver_version=version,
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
    ) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver {solver_key}:{version} not found",
        ) from err


@router.get(
    "/{solver_key:path}/releases/{version}/ports",
    response_model=OnePage[SolverPort],
    responses=_SOLVER_STATUS_CODES,
    description=create_route_description(
        base="Lists inputs and outputs of a given solver",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5"),
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.7.1", "`version_display` field in the response"
            ),
        ],
    ),
)
async def list_solver_ports(
    solver_key: SolverKeyId,
    version: VersionStr,
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    ports = await catalog_service.get_service_ports(
        name=solver_key,
        version=version,
    )

    solver_ports = [SolverPort.model_validate(port.model_dump()) for port in ports]
    return OnePage[SolverPort].model_validate(dict(items=solver_ports))


@router.get(
    "/{solver_key:path}/releases/{version}/pricing_plan",
    response_model=ServicePricingPlanGetLegacy,
    responses=_SOLVER_STATUS_CODES,
    description=create_route_description(
        base="Gets solver pricing plan",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7"),
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.7.1", "`version_display` field in the response"
            ),
        ],
    ),
)
async def get_solver_pricing_plan(
    solver_key: SolverKeyId,
    version: VersionStr,
    user_id: Annotated[int, Depends(get_current_user_id)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    assert user_id
    assert product_name
    pricing_plan_or_none = await webserver_api.get_service_pricing_plan(
        solver_key=solver_key, version=version
    )
    # NOTE: pricing_plan_or_none https://github.com/ITISFoundation/osparc-simcore/issues/6901
    assert pricing_plan_or_none  # nosec
    return pricing_plan_or_none
