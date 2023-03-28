from dataclasses import dataclass
from typing import AsyncIterator

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from models_library.services import ServiceKey
from pydantic import PositiveInt
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_latest,
    services_meta_data,
)
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)

from ..db import get_database_engine
from .settings import StudiesDispatcherSettings, get_plugin_settings

_EVERYONE_GROUP_ID = 1
LARGEST_PAGE_SIZE = 1000


@dataclass
class ServiceMetaData:
    # acts as adapter bewteen RowProxy and ServiceGet BaseModel
    key: str
    version: str
    title: str  # alias for 'name'
    description: str
    thumbnail: str
    file_extensions: list[str]


async def _get_service_filetypes(conn: SAConnection) -> dict[ServiceKey, list[str]]:
    query = sa.select(
        services_consume_filetypes.c.service_key,
        sa.func.array_agg(
            sa.func.distinct(services_consume_filetypes.c.filetype)
        ).label("file_extensions"),
    ).group_by(services_consume_filetypes.c.service_key)

    result = await conn.execute(query)
    rows = await result.fetchall()

    return {row.service_key: row.file_extensions for row in rows}


async def iter_latest_osparc_services(
    app: web.Application,
    *,
    page_number: PositiveInt = 1,  # 1-based
    page_size: PositiveInt = LARGEST_PAGE_SIZE,
) -> AsyncIterator[ServiceMetaData]:
    assert page_number >= 1  # nosec
    assert ((page_number - 1) * page_size) >= 0  # nosec

    engine: Engine = get_database_engine(app)
    settings: StudiesDispatcherSettings = get_plugin_settings(app)

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
            (
                services_latest.c.key.like("simcore/services/dynamic/%%")
                | (services_latest.c.key.like("simcore/services/comp/%%"))
            )
            & (services_access_rights.c.gid == _EVERYONE_GROUP_ID)
            & (services_access_rights.c.execute_access == True)
            & (services_access_rights.c.product_name == "osparc")
        )
    )

    # pagination
    query = query.limit(page_size).offset((page_number - 1) * page_size)

    async with engine.acquire() as conn:
        service_filetypes = await _get_service_filetypes(conn)

        async for row in await conn.execute(query):
            yield ServiceMetaData(
                key=row.key,
                version=row.version,
                title=row.name,
                description=row.description,
                thumbnail=row.thumbnail or settings.STUDIES_DEFAULT_SERVICE_THUMBNAIL,
                file_extensions=service_filetypes.get(row.key, []),
            )
