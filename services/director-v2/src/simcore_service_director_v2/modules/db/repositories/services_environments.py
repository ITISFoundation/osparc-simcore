from models_library.services import ServiceKey
from simcore_postgres_database.models.services_environments import VendorSecretsDict
from simcore_postgres_database.utils_services_environments import get_vendor_secrets

from ._base import BaseRepository


class ServicesEnvironmentsRepository(BaseRepository):
    async def get_vendor_secrets(self, service_key: ServiceKey) -> VendorSecretsDict:
        async with self.db_engine.acquire() as conn:
            oenvs = await get_vendor_secrets(
                conn, vendor_service_key=service_key, normalize_names=True
            )
            return oenvs
