from typing import Literal

from models_library.products import ProductName
from models_library.services import ServiceKey, ServiceVersion
from simcore_postgres_database.models.services_environments import VENDOR_SECRET_PREFIX
from simcore_postgres_database.utils_services_environments import (
    VendorSecret,
    get_vendor_secrets,
)

from ._base import BaseRepository


class ServicesEnvironmentsRepository(BaseRepository):
    """
    Access to Vendor settings for a service
    """

    async def get_vendor_secrets(
        self,
        service_key: ServiceKey,
        service_version: ServiceVersion | Literal["latest"],
        product_name: ProductName,
    ) -> dict[str, VendorSecret]:
        """Fetches vendor secrets for a service using normalized names"""
        async with self.db_engine.connect() as conn:
            vendor_secrets = await get_vendor_secrets(
                conn,
                product_name=product_name,
                vendor_service_key=service_key,
                vendor_service_version=service_version,
                normalize_names=True,
            )
            assert all(  # nosec
                self.is_vendor_secret_identifier(key) for key in vendor_secrets
            )

            return vendor_secrets

    @classmethod
    def is_vendor_secret_identifier(cls, identifier: str) -> bool:
        return identifier.startswith(VENDOR_SECRET_PREFIX)
