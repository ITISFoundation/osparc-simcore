from sqlalchemy.sql import select

from ._protocols import DBConnection
from .models.services_environments import (
    VENDOR_SECRET_PREFIX,
    VendorSecretsDict,
    services_vendor_secrets,
)


async def get_vendor_secrets(
    conn: DBConnection,
    vendor_service_key: str,  # NOTE: ServiceKey is defined in model_library
    *,
    normalize_names: bool = True,
) -> VendorSecretsDict:
    secrets: VendorSecretsDict = {}

    secrets_map = await conn.scalar(
        select(services_vendor_secrets.c.secrets_map).where(
            services_vendor_secrets.c.service_key == vendor_service_key
        )
    )
    if secrets_map is not None:
        secrets = dict(secrets_map)

    if normalize_names:
        for key in secrets.keys():
            if not key.startswith(VENDOR_SECRET_PREFIX):
                secrets[VENDOR_SECRET_PREFIX + key.upper()] = secrets[key]

        assert all(key.startswith(VENDOR_SECRET_PREFIX) for key in secrets)  # nosec

    assert all(  # nosec
        isinstance(value, (bool, int, str, float)) for value in secrets.values()
    )

    return secrets
