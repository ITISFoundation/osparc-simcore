from dataclasses import dataclass

from models_library.api_schemas_catalog.services import ServiceListFilters
from models_library.basic_types import VersionStr
from models_library.rest_pagination import (
    PageLimitInt,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.services_enums import ServiceType

from .models.schemas.programs import Program, ProgramKeyId
from .services_rpc.catalog import CatalogService


@dataclass(frozen=True, kw_only=True)
class ProgramService:
    catalog_service: CatalogService

    async def get_program(
        self,
        *,
        name: ProgramKeyId,
        version: VersionStr,
    ) -> Program:
        service = await self.catalog_service.get(
            name=name,
            version=version,
        )
        assert service.service_type == ServiceType.DYNAMIC  # nosec

        return Program.create_from_service(service)

    async def list_latest_programs(
        self,
        *,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[Program], PageMetaInfoLimitOffset]:
        page, page_meta = await self.catalog_service.list_latest_releases(
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            filters=ServiceListFilters(service_type=ServiceType.DYNAMIC),
        )

        items = [Program.create_from_service(service) for service in page]
        return items, page_meta

    async def list_program_history(
        self,
        *,
        program_key: ProgramKeyId,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[Program], PageMetaInfoLimitOffset]:
        page, page_meta = await self.catalog_service.list_release_history_latest_first(
            filter_by_service_key=program_key,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )
        if len(page) == 0:
            return [], page_meta

        program_instance = await self.catalog_service.get(
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
