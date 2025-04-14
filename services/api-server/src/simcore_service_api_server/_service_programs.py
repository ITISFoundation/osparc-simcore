from dataclasses import dataclass

from models_library.basic_types import VersionStr
from models_library.services_enums import ServiceType
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from simcore_service_api_server.models.schemas.programs import Program, ProgramKeyId

from .services_rpc.catalog import CatalogService


@dataclass
class ProgramService(SingletonInAppStateMixin):
    app_state_name = "ProgramService"

    async def get_program(
        self,
        *,
        catalog_service: CatalogService,
        user_id: int,
        name: ProgramKeyId,
        version: VersionStr,
        product_name: str,
    ) -> Program:
        service = await catalog_service.get(
            user_id=user_id,
            service_key=name,
            service_version=version,
            product_name=product_name,
        )
        assert (  # nosec
            service.service_type == ServiceType.DYNAMIC
        ), "Expected by ProgramName regex"

        return Program.create_from_service(service)
