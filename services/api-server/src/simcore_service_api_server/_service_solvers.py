from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_catalog.services import ServiceListFilters
from models_library.basic_types import VersionStr
from models_library.products import ProductName
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
)
from models_library.services_enums import ServiceType
from models_library.users import UserID
from pydantic import NonNegativeInt, PositiveInt

from .models.schemas.solvers import Solver, SolverKeyId
from .services_rpc.catalog import CatalogService

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


class SolverService:
    _catalog_service: CatalogService

    def __init__(self, catalog_service: Annotated[CatalogService, Depends()]):
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
        releases, _ = await self._catalog_service.list_release_history_latest_first(
            user_id=user_id,
            service_key=solver_key,
            product_name=product_name,
            offset=0,
            limit=1,
        )

        assert len(releases) == 1  # nosec
        service = await self._catalog_service.get(
            user_id=user_id,
            name=solver_key,
            version=releases[0].version,
            product_name=product_name,
        )

        return Solver.create_from_service(service)

    async def solver_release_history(
        self,
        *,
        user_id: UserID,
        solver_key: SolverKeyId,
        product_name: ProductName,
        offset: NonNegativeInt,
        limit: PositiveInt,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:

        releases, page_meta = (
            await self._catalog_service.list_release_history_latest_first(
                user_id=user_id,
                service_key=solver_key,
                product_name=product_name,
                offset=offset,
                limit=limit,
            )
        )

        service_instance = await self._catalog_service.get(
            user_id=user_id,
            name=solver_key,
            version=releases[-1].version,
            product_name=product_name,
        )

        return [
            Solver.create_from_service_release(
                service_key=service_instance.key,
                description=service_instance.description,
                contact=service_instance.contact,
                name=service_instance.name,
                service=service,
            )
            for service in releases
        ], page_meta

    async def latest_solvers(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        offset: NonNegativeInt,
        limit: PositiveInt,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:
        """Lists the latest solvers with pagination."""
        services, page_meta = await self._catalog_service.list_latest_releases(
            user_id=user_id,
            product_name=product_name,
            offset=offset,
            limit=limit,
            filters=ServiceListFilters(service_type=ServiceType.COMPUTATIONAL),
        )

        solvers = [Solver.create_from_service(service) for service in services]
        return solvers, page_meta
