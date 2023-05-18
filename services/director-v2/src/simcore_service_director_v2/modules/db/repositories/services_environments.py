from typing import Any

from models_library.services import ServiceKey
from simcore_postgres_database.utils_services_environments import (
    VENDOR_SECRET_PREFIX,
    get_vendor_secrets,
)

from ._base import BaseRepository


class ServicesEnvironmentsRepository(BaseRepository):
    async def get_vendor_secrets(self, service_key: ServiceKey) -> dict[str, Any]:
        async with self.db_engine.acquire() as conn:
            vendor_secrets = await get_vendor_secrets(
                conn, vendor_service_key=service_key, normalize_names=True
            )

            # normalize_names = True
            assert all(
                self.is_vendor_secret_identifier(key) for key in vendor_secrets
            )  # nosec

            return vendor_secrets

    def is_vendor_secret_identifier(self, identifier) -> bool:
        return identifier.startswith(VENDOR_SECRET_PREFIX)
