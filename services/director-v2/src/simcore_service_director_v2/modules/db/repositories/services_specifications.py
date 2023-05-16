from models_library.services import ServiceKey
from simcore_postgres_database.models.services_environments import (
    OsparcEnvironmentsDict,
)
from simcore_postgres_database.utils_services_specifications import (
    get_vendor_environments,
)

from ._base import BaseRepository


class ServicesSpecificationsRepository(BaseRepository):
    async def get_vendor_environments(
        self, service_key: ServiceKey
    ) -> OsparcEnvironmentsDict:
        async with self.db_engine.acquire() as conn:
            oenvs = await get_vendor_environments(
                conn, vendor_service_key=service_key, normalize_names=True
            )
            return oenvs
