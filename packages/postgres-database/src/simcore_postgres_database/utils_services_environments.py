from typing import Any

from sqlalchemy.sql import select

from ._protocols import DBConnection
from .models.services_environments import VENDOR_SECRET_PREFIX, services_vendor_secrets


async def get_vendor_secrets(
    conn: DBConnection,
    vendor_service_key: str,  # NOTE: ServiceKey is defined in model_library
    *,
    normalize_names: bool = True,
) -> dict[str, Any]:

    # NOTE: a secret value can be Any! even a json!
    secrets: dict[str, Any] = {}

    secrets_map = await conn.scalar(
        select(services_vendor_secrets.c.secrets_map).where(
            services_vendor_secrets.c.service_key == vendor_service_key
        )
    )
    if secrets_map is not None:
        secrets = dict(secrets_map)

    if normalize_names:
        for key in list(secrets.keys()):
            if not key.startswith(VENDOR_SECRET_PREFIX):
                secrets[VENDOR_SECRET_PREFIX + key.upper()] = secrets.pop(key)

        assert all(key.startswith(VENDOR_SECRET_PREFIX) for key in secrets)  # nosec

    assert all(  # nosec
        isinstance(value, (bool, int, str, float)) for value in secrets.values()
    )

    return secrets
