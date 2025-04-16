from typing import Annotated

from common_library.pagination_tools import iter_pagination_params
from fastapi import Depends
from models_library.basic_types import VersionStr
from models_library.products import ProductName
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.services_enums import ServiceType
from models_library.services_history import ServiceRelease
from models_library.users import UserID
from packaging.version import Version

from .models.schemas.solvers import Solver, SolverKeyId
from .services_rpc.catalog import CatalogService

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


class SolverService:
    _catalog_service: CatalogService

    def __init__(
        self, catalog_service: Annotated[CatalogService, Depends(CatalogService)]
    ):
        self._catalog_service = catalog_service

    async def get_solver(
        self,
        *,
        user_id: UserID,
        name: SolverKeyId,
        version: VersionStr,
        product_name: ProductName,
    ) -> Solver:
        service = await self._catalog_service.get(
            user_id=user_id,
            name=name,
            version=version,
            product_name=product_name,
        )
        assert (  # nosec
            service.service_type == ServiceType.COMPUTATIONAL
        ), "Expected by SolverName regex"

        return Solver.create_from_service(service)

    async def get_latest_release(
        self,
        *,
        user_id: int,
        solver_key: SolverKeyId,
        product_name: str,
    ) -> Solver:
        service_releases: list[ServiceRelease] = []
        for page_params in iter_pagination_params(limit=DEFAULT_PAGINATION_LIMIT):
            releases, page_meta = await self._catalog_service.list_release_history(
                user_id=user_id,
                service_key=solver_key,
                product_name=product_name,
                offset=page_params.offset,
                limit=page_params.limit,
            )
            page_params.total_number_of_items = page_meta.total
            service_releases.extend(releases)

        release = sorted(service_releases, key=lambda s: Version(s.version))[-1]
        service = await self._catalog_service.get(
            user_id=user_id,
            name=solver_key,
            version=release.version,
            product_name=product_name,
        )

        return Solver.create_from_service(service)
