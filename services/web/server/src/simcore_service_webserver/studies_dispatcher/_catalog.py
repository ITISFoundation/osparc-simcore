from dataclasses import dataclass
from typing import AsyncIterator

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_latest,
    services_meta_data,
)

from ..db import get_database_engine

_EVERYONE_GROUP_ID = 1


@dataclass
class ServiceMetaData:
    # acts as adapter bewteen RowProxy and ServiceGet BaseModel
    key: str
    version: str
    title: str  # alias for 'name'
    description: str
    thumbnail: str


async def list_latest_osparc_dynamic_services(
    app: web.Application,
) -> AsyncIterator[ServiceMetaData]:
    engine: Engine = get_database_engine(app)

    query = (
        sa.select(
            [
                services_meta_data.c.key,
                services_meta_data.c.version,
                services_meta_data.c.name,
                services_meta_data.c.description,
                services_meta_data.c.thumbnail,
            ]
        )
        .select_from(
            services_latest.join(
                services_meta_data,
                (services_meta_data.c.key == services_latest.c.key)
                & (services_meta_data.c.version == services_latest.c.version),
            ).join(
                services_access_rights,
                (services_meta_data.c.key == services_access_rights.c.key)
                & (services_meta_data.c.version == services_access_rights.c.version),
            )
        )
        .where(
            services_latest.c.key.like("simcore/services/dynamic/%%")
            & (services_access_rights.c.gid == _EVERYONE_GROUP_ID)
            & (services_access_rights.c.execute_access == True)
            & (services_access_rights.c.product_name == "osparc")
        )
    )

    async with engine.acquire() as conn:
        async for row in await conn.execute(query):
            yield ServiceMetaData(
                key=row.key,
                version=row.version,
                title=row.name,
                description=row.description,
                thumbnail=row.thumbnail,
            )
