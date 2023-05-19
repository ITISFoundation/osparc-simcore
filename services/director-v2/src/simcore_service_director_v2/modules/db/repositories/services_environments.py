from models_library.services import ServiceKey
from models_library.users import UserID
from pydantic import EmailStr
from simcore_postgres_database.utils_services_environments import (
    VENDOR_SECRET_PREFIX,
    VendorSecret,
    get_vendor_secrets,
)

from ._base import BaseRepository


class ServicesEnvironmentsRepository(BaseRepository):
    async def get_vendor_secrets(
        self, service_key: ServiceKey
    ) -> dict[str, VendorSecret]:
        """Fetches vendor secrets for a service using normalized names"""
        async with self.db_engine.acquire() as conn:
            vendor_secrets: dict[str, VendorSecret] = await get_vendor_secrets(
                conn, vendor_service_key=service_key, normalize_names=True
            )

            # NOTE: normalize_names = True
            assert all(  # nosec
                self.is_vendor_secret_identifier(key) for key in vendor_secrets
            )  # nosec

            return vendor_secrets

    def is_vendor_secret_identifier(self, identifier: str) -> bool:
        return identifier.startswith(VENDOR_SECRET_PREFIX)

    async def get_user_role(self, user_id: UserID):
        ...

    async def get_user_email(self, user_id: UserID) -> EmailStr:
        ...
