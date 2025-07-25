from collections.abc import Iterable

from aiohttp import web
from models_library.services_types import ServiceKey, ServiceVersion
from simcore_postgres_database.models.services import (
    services_meta_data,
)
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from simcore_service_webserver.functions._services_metadata._errors import (
    ServiceMetadataNotFoundError,
)
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncConnection

from ...db.plugin import get_asyncpg_engine
from ._models import ServiceMetadata


async def batch_service_metadata(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    keys_and_versions: Iterable[tuple[ServiceKey, ServiceVersion]],
) -> dict[tuple[ServiceKey, ServiceVersion], ServiceMetadata]:
    keys_and_versions = list(keys_and_versions)
    if not keys_and_versions:
        return {}

    query = select(
        services_meta_data.c.key,
        services_meta_data.c.version,
        services_meta_data.c.thumbnail,
    ).where(
        tuple_(services_meta_data.c.key, services_meta_data.c.version).in_(
            keys_and_versions
        )
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

        return {
            (row.key, row.version): ServiceMetadata.model_validate(
                row, from_attributes=True
            )
            for row in rows
        }


async def get_service_metadata(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    key: ServiceKey,
    version: ServiceVersion,
) -> ServiceMetadata:
    query = select(
        services_meta_data.c.key,
        services_meta_data.c.version,
        services_meta_data.c.thumbnail,
    ).where(
        tuple_(services_meta_data.c.key, services_meta_data.c.version) == (key, version)
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(query)
        row = result.one_or_none()
        if row is None:
            raise ServiceMetadataNotFoundError(key=key, version=version)

        return ServiceMetadata.model_validate(row, from_attributes=True)
