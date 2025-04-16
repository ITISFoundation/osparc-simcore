from typing import Annotated

from fastapi import Depends
from models_library.basic_types import VersionStr
from models_library.products import ProductName
from models_library.services_enums import ServiceType
from models_library.users import UserID

from .models.schemas.solvers import Solver, SolverKeyId
from .services_rpc.catalog import CatalogService


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
            service_key=name,
            service_version=version,
            product_name=product_name,
        )
        assert (  # nosec
            service.service_type == ServiceType.COMPUTATIONAL
        ), "Expected by SolverName regex"

        return Solver.create_from_service(service)
