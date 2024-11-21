import logging
from contextlib import suppress
from dataclasses import dataclass
from typing import AsyncIterator

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from models_library.groups import EVERYONE_GROUP_ID
from models_library.services import ServiceKey, ServiceVersion
from pydantic import HttpUrl, PositiveInt, TypeAdapter, ValidationError
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_meta_data,
)
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from simcore_postgres_database.utils_services import create_select_latest_services_query

from ..db.plugin import get_database_engine
from ._errors import ServiceNotFound
from .settings import StudiesDispatcherSettings, get_plugin_settings

LARGEST_PAGE_SIZE = 1000

_logger = logging.getLogger(__name__)


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
        ).label("list_of_file_types"),
    ).group_by(services_consume_filetypes.c.service_key)

    result = await conn.execute(query)
    rows = await result.fetchall()

    return {row.service_key: row.list_of_file_types for row in rows}


async def iter_latest_product_services(
    app: web.Application,
    *,
    product_name: str,
    page_number: PositiveInt = 1,  # 1-based
    page_size: PositiveInt = LARGEST_PAGE_SIZE,
) -> AsyncIterator[ServiceMetaData]:
    assert page_number >= 1  # nosec
    assert ((page_number - 1) * page_size) >= 0  # nosec

    engine: Engine = get_database_engine(app)
    settings: StudiesDispatcherSettings = get_plugin_settings(app)

    # Select query for latest version of the service
    latest_services = create_select_latest_services_query().alias("latest_services")

    query = (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
            services_meta_data.c.name,
            services_meta_data.c.description,
            services_meta_data.c.thumbnail,
            services_meta_data.c.deprecated,
        )
        .select_from(
            latest_services.join(
                services_meta_data,
                (services_meta_data.c.key == latest_services.c.key)
                & (services_meta_data.c.version == latest_services.c.latest),
            ).join(
                services_access_rights,
                (services_meta_data.c.key == services_access_rights.c.key)
                & (services_meta_data.c.version == services_access_rights.c.version),
            )
        )
        .where(
            (
                services_meta_data.c.key.like("simcore/services/dynamic/%%")
                | (services_meta_data.c.key.like("simcore/services/comp/%%"))
            )
            & (services_meta_data.c.deprecated.is_(None))
            & (services_access_rights.c.gid == EVERYONE_GROUP_ID)
            & (services_access_rights.c.execute_access.is_(True))
            & (services_access_rights.c.product_name == product_name)
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
                thumbnail=row.thumbnail
                or f"{settings.STUDIES_DEFAULT_SERVICE_THUMBNAIL}",
                file_extensions=service_filetypes.get(row.key, []),
            )


@dataclass
class ValidService:
    key: str
    version: str
    title: str
    is_public: bool
    thumbnail: HttpUrl | None  # nullable


@log_decorator(_logger, level=logging.DEBUG)
async def validate_requested_service(
    app: web.Application,
    *,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ValidService:
    engine: Engine = get_database_engine(app)

    async with engine.acquire() as conn:
        query = sa.select(
            services_meta_data.c.name,
            services_meta_data.c.key,
            services_meta_data.c.thumbnail,
        ).where(
            (services_meta_data.c.key == service_key)
            & (services_meta_data.c.version == service_version)
        )

        result = await conn.execute(query)
        row = await result.fetchone()

        if row is None:
            raise ServiceNotFound(
                service_key=service_key, service_version=service_version
            )

        assert row.key == service_key  # nosec

        query = (
            sa.select(services_consume_filetypes.c.is_guest_allowed)
            .where(
                (services_consume_filetypes.c.service_key == service_key)
                & (services_consume_filetypes.c.is_guest_allowed.is_(True))
            )
            .limit(1)
        )

        is_guest_allowed = await conn.scalar(query)

        thumbnail_or_none = None
        if row.thumbnail is not None:
            with suppress(ValidationError):
                thumbnail_or_none = TypeAdapter(HttpUrl).validate_python(row.thumbnail)

        return ValidService(
            key=service_key,
            version=service_version,
            is_public=bool(is_guest_allowed),
            title=row.name or service_key.split("/")[-1],
            thumbnail=thumbnail_or_none,
        )
