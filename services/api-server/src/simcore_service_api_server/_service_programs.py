from typing import Annotated

from fastapi import Depends
from models_library.basic_types import VersionStr
from models_library.services_enums import ServiceType

from .models.schemas.programs import Program, ProgramKeyId
from .services_rpc.catalog import CatalogService


class ProgramService:
    _catalog_service: CatalogService

    def __init__(self, _catalog_service: Annotated[CatalogService, Depends()]):
        self._catalog_service = _catalog_service

    async def get_program(
        self,
        *,
        user_id: int,
        name: ProgramKeyId,
        version: VersionStr,
        product_name: str,
    ) -> Program:
        service = await self._catalog_service.get(
            user_id=user_id,
            name=name,
            version=version,
            product_name=product_name,
        )
        assert service.service_type == ServiceType.DYNAMIC  # nosec

        return Program.create_from_service(service)
