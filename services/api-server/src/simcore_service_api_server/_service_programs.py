from models_library.api_schemas_catalog.services import ServiceListFilters
from models_library.basic_types import VersionStr
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.services_enums import ServiceType
from pydantic import NonNegativeInt, PositiveInt

from .models.schemas.programs import Program, ProgramKeyId
from .services_rpc.catalog import CatalogService


class ProgramService:
    _catalog_service: CatalogService

    def __init__(self, _catalog_service: CatalogService):
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
            name=name,
            version=version,
        )
        assert service.service_type == ServiceType.DYNAMIC  # nosec

        return Program.create_from_service(service)

    async def list_latest_programs(
        self,
        *,
        user_id: int,
        product_name: str,
        offset: NonNegativeInt,
        limit: PositiveInt,
    ) -> tuple[list[Program], PageMetaInfoLimitOffset]:
        page, page_meta = await self._catalog_service.list_latest_releases(
            offset=offset,
            limit=limit,
            filters=ServiceListFilters(service_type=ServiceType.DYNAMIC),
        )

        items = [Program.create_from_service(service) for service in page]
        return items, page_meta

    async def list_program_history(
        self,
        *,
        user_id: int,
        program_key: ProgramKeyId,
        product_name: str,
        offset: NonNegativeInt,
        limit: PositiveInt,
    ) -> tuple[list[Program], PageMetaInfoLimitOffset]:
        page, page_meta = await self._catalog_service.list_release_history(
            service_key=program_key,
            offset=offset,
            limit=limit,
        )

        program_instance = await self._catalog_service.get(
            name=program_key,
            version=page[-1].version,
        )

        items = [
            Program.create_from_service_release(
                service=service,
                service_key=program_instance.key,
                description=program_instance.description,
                name=program_instance.name,
            )
            for service in page
        ]
        return items, page_meta
