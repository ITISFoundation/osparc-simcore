from dataclasses import dataclass

from fastapi import FastAPI
from models_library.basic_types import VersionStr
from models_library.services_enums import ServiceType
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from .models.schemas.programs import Program, ProgramKeyId
from .services_rpc.catalog import CatalogService


@dataclass
class ProgramService(SingletonInAppStateMixin):
    app_state_name = "ProgramService"
    _catalog_service: CatalogService | None = None

    @property
    def catalog_service(self) -> CatalogService:
        assert self._catalog_service, "ProgramService not initialized"  # nosec
        return self._catalog_service

    async def get_program(
        self,
        *,
        user_id: int,
        name: ProgramKeyId,
        version: VersionStr,
        product_name: str,
    ) -> Program:
        service = await self.catalog_service.get(
            user_id=user_id,
            service_key=name,
            service_version=version,
            product_name=product_name,
        )
        assert service.service_type == ServiceType.DYNAMIC  # nosec

        return Program.create_from_service(service)


def setup(app: FastAPI):
    ProgramService().set_to_app_state(app=app)
