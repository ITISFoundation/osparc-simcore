from sqlalchemy.sql import select

from ._protocols import DBConnection
from .models.services_environments import (
    OsparcEnvironmentsDict,
    services_vendor_environments,
)


async def get_vendor_environments(
    connection: DBConnection, vendor_service_key: str
) -> OsparcEnvironmentsDict:

    environments = await connection.scalar(
        select([services_vendor_environments.c.identifiers_map]).where(
            services_vendor_environments.c.service_key == vendor_service_key
        )
    )

    return environments
