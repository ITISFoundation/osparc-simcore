from typing import Literal

from models_library.products import ProductName
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import EmailStr, parse_obj_as
from simcore_postgres_database.utils_services_environments import (
    VENDOR_SECRET_PREFIX,
    VendorSecret,
    get_vendor_secrets,
)
from simcore_postgres_database.utils_users import UsersRepo

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
        async with self.db_engine.acquire() as conn:
            vendor_secrets: dict[str, VendorSecret] = await get_vendor_secrets(
                conn,
                product_name=product_name,
                vendor_service_key=service_key,
                vendor_service_version=service_version,
                normalize_names=True,
            )

            # NOTE: normalize_names = True
            assert all(  # nosec
                self.is_vendor_secret_identifier(key) for key in vendor_secrets
            )  # nosec

            return vendor_secrets

    @classmethod
    def is_vendor_secret_identifier(cls, identifier: str) -> bool:
        return identifier.startswith(VENDOR_SECRET_PREFIX)

    async def get_user_role(self, user_id: UserID):
        async with self.db_engine.acquire() as conn:
            return UsersRepo().get_role(conn, user_id=user_id)

    async def get_user_email(self, user_id: UserID) -> EmailStr:
        async with self.db_engine.acquire() as conn:
            email = UsersRepo().get_email(conn, user_id=user_id)
            return parse_obj_as(EmailStr, email)
