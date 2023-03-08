from sqlalchemy.sql import select

from ._protocols import DBConnection
from .models.services_environments import (
    OsparcEnvironmentsDict,
    services_vendor_environments,
)


async def get_vendor_environments(
    connection: DBConnection, vendor_service_key: str
) -> OsparcEnvironmentsDict:
    # we know it is unique
    identifiers_map = await connection.scalar(
        select([services_vendor_environments.c.identifiers_map]).where(
            services_vendor_environments.c.service_key == vendor_service_key
        )
    )
    environments = {}
    if identifiers_map is not None:
        environments = dict(identifiers_map)

    assert all(key.startswith("OSPARC_ENVIRONMENT_") for key in environments)  # nosec
    assert all(  # nosec
        isinstance(value, (bool, int, str, float)) for value in environments.values()
    )

    return environments
