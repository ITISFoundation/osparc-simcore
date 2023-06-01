from typing import Final, TypeAlias

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER

from ._protocols import DBConnection
from .models.services_environments import VENDOR_SECRET_PREFIX, services_vendor_secrets

# This constraint is to avoid deserialization issues after substitution!
VendorSecret: TypeAlias = bool | int | float | str

LATEST: Final[str] = "latest"


async def get_vendor_secrets(
    conn: DBConnection,
    vendor_service_key: str,  # NOTE: ServiceKey is defined in model_library
    vendor_service_version: str = LATEST,  # NOTE: ServiceVersion is defined in model_library
    *,
    normalize_names: bool = True,
) -> dict[str, VendorSecret]:

    select_stmt = sa.select(services_vendor_secrets.c.secrets_map)
    where_stmt = services_vendor_secrets.c.service_key == vendor_service_key

    def _version(column_or_value):
        # converts version value string to array[integer] that can be compared
        return sa.func.string_to_array(column_or_value, ".").cast(ARRAY(INTEGER))

    if vendor_service_version == LATEST:
        latest_version = sa.select(
            sa.func.array_to_string(
                sa.func.max(_version(services_vendor_secrets.c.service_from_version)),
                ".",
            )
        ).where(services_vendor_secrets.c.service_key == vendor_service_key)

        where_stmt &= (
            services_vendor_secrets.c.service_from_version == latest_version.subquery()
        )

        query = select_stmt.where(where_stmt)
    else:
        assert len([int(p) for p in vendor_service_version.split(".")]) == 3  # nosec

        where_stmt &= _version(
            services_vendor_secrets.c.service_from_version
        ) <= _version(vendor_service_version)

        query = (
            select_stmt.where(where_stmt)
            .order_by(_version(services_vendor_secrets.c.service_from_version).desc())
            .limit(1)
        )

    secrets_map = await conn.scalar(query)
    secrets: dict[str, VendorSecret] = {}

    if secrets_map is not None:
        secrets = dict(secrets_map)

    if secrets_map and normalize_names:
        for key in list(secrets.keys()):
            if not key.startswith(VENDOR_SECRET_PREFIX):
                secrets[VENDOR_SECRET_PREFIX + key.upper()] = secrets.pop(key)

        assert all(key.startswith(VENDOR_SECRET_PREFIX) for key in secrets)  # nosec

        assert all(  # nosec
            isinstance(value, (bool, int, str, float)) for value in secrets.values()
        )

    return secrets
