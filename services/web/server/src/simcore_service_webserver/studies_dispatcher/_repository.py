import logging
from collections.abc import AsyncIterator

import sqlalchemy as sa
from models_library.services import ServiceVersion
from pydantic import TypeAdapter, ValidationError
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.base_repository import BaseRepository
from ._models import ViewerInfo

_logger = logging.getLogger(__name__)


def _version(column_or_value):
    """Converts version value string to array[integer] that can be compared."""
    return sa.func.string_to_array(column_or_value, ".").cast(ARRAY(INTEGER))


def create_viewer_info_from_db(row: Row) -> ViewerInfo:
    """Create ViewerInfo instance from database row."""
    return ViewerInfo(
        key=row.service_key,
        version=row.service_version,
        filetype=row.filetype,
        label=row.service_display_name or row.service_key.split("/")[-1],
        input_port_key=row.service_input_port,
        is_guest_allowed=row.is_guest_allowed,
    )


class StudiesDispatcherRepository(BaseRepository):
    async def list_viewers_info(
        self,
        connection: AsyncConnection | None = None,
        *,
        file_type: str | None = None,
        only_default: bool = False,
    ) -> list[ViewerInfo]:
        """List viewer services that can consume the given file type."""

        async def _iter_viewers() -> AsyncIterator[ViewerInfo]:
            query = services_consume_filetypes.select()
            if file_type:
                query = query.where(services_consume_filetypes.c.filetype == file_type)

            query = query.order_by("filetype", "preference_order")

            if file_type and only_default:
                query = query.limit(1)

            _logger.debug("Listing viewers:\n%s", query)

            async with pass_or_acquire_connection(self.engine, connection) as conn:
                result = await conn.stream(query)

                listed_filetype = set()
                async for row in result:
                    try:
                        # TODO: filter in database (see test_list_default_compatible_services )
                        if only_default and row.filetype in listed_filetype:
                            continue
                        listed_filetype.add(row.filetype)
                        consumer = create_viewer_info_from_db(row)
                        yield consumer

                    except ValidationError as err:
                        _logger.warning("Review invalid service metadata %s: %s", row, err)

        return [viewer async for viewer in _iter_viewers()]

    async def get_default_viewer_for_filetype(
        self,
        connection: AsyncConnection | None = None,
        *,
        file_type: str,
    ) -> ViewerInfo | None:
        """Get the default viewer for a specific file type."""
        viewers = await self.list_viewers_info(connection=connection, file_type=file_type, only_default=True)
        return viewers[0] if viewers else None

    async def find_compatible_viewer(
        self,
        connection: AsyncConnection | None = None,
        *,
        file_type: str,
        service_key: str,
        service_version: str,
    ) -> ViewerInfo | None:
        """Find a compatible viewer service for the given file type, service key, and version."""

        query = (
            services_consume_filetypes.select()
            .where(
                (services_consume_filetypes.c.filetype == file_type)
                & (services_consume_filetypes.c.service_key == service_key)
                & (_version(services_consume_filetypes.c.service_version) <= _version(service_version))
            )
            .order_by(_version(services_consume_filetypes.c.service_version).desc())
            .limit(1)
        )

        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(query)
            row = result.one_or_none()
            if row:
                view = create_viewer_info_from_db(row)
                view.version = TypeAdapter(ServiceVersion).validate_python(service_version)
                return view

        return None
