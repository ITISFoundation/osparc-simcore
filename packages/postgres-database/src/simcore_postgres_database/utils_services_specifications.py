from sqlalchemy.sql import select

from ._protocols import DBConnection
from .models.services_environments import (
    OsparcEnvironmentsDict,
    services_vendor_environments,
)


async def get_vendor_environments(
    connection: DBConnection,
    vendor_service_key: str,  # NOTE: ServiceKey is defined in model_library
    *,
    normalize_names: bool = True,
) -> OsparcEnvironmentsDict:
    # we know it is unique
    identifiers_map = await connection.scalar(
        select(services_vendor_environments.c.identifiers_map).where(
            services_vendor_environments.c.service_key == vendor_service_key
        )
    )
    environments: OsparcEnvironmentsDict = {}
    if identifiers_map is not None:
        environments = dict(identifiers_map)

    if normalize_names:
        new_environments = {}
        for key, value in environments.items():
            if not key.startswith("OSPARC_ENVIRONMENT_"):
                key = f"OSPARC_ENVIRONMENT_{key.upper()}"
            new_environments[key] = value
        environments = new_environments
        assert all(  # nosec
            key.startswith("OSPARC_ENVIRONMENT_") for key in environments
        )

    assert all(  # nosec
        isinstance(value, (bool, int, str, float)) for value in environments.values()
    )

    return environments
