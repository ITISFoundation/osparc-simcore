import logging
import uuid
from collections import deque
from functools import lru_cache

import sqlalchemy as sa
from aiohttp import web
from models_library.services import ServiceVersion
from models_library.utils.pydantic_tools_extension import parse_obj_or_none
from pydantic import ByteSize, TypeAdapter, ValidationError
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER

from ..db.plugin import get_database_engine
from ._errors import FileToLarge, IncompatibleService
from ._models import ViewerInfo
from .settings import get_plugin_settings

_BASE_UUID = uuid.UUID("ca2144da-eabb-4daf-a1df-a3682050e25f")


_logger = logging.getLogger(__name__)


@lru_cache
def compose_uuid_from(*values) -> uuid.UUID:
    composition: str = "/".join(map(str, values))
    new_uuid = uuid.uuid5(_BASE_UUID, composition)
    return new_uuid


async def list_viewers_info(
    app: web.Application, file_type: str | None = None, *, only_default: bool = False
) -> list[ViewerInfo]:
    #
    # TODO: These services MUST be shared with EVERYBODY! Setup check on startup and fill
    #       with !?
    #
    consumers: deque = deque()

    async with get_database_engine(app).acquire() as conn:
        # FIXME: ADD CONDITION: service MUST be shared with EVERYBODY!
        query = services_consume_filetypes.select()
        if file_type:
            query = query.where(services_consume_filetypes.c.filetype == file_type)

        query = query.order_by("filetype", "preference_order")

        if file_type and only_default:
            query = query.limit(1)

        _logger.debug("Listing viewers:\n%s", query)

        listed_filetype = set()
        async for row in await conn.execute(query):
            try:
                # TODO: filter in database (see test_list_default_compatible_services )
                if only_default:
                    if row["filetype"] in listed_filetype:
                        continue
                listed_filetype.add(row["filetype"])
                consumer = ViewerInfo.create_from_db(row)
                consumers.append(consumer)

            except ValidationError as err:
                _logger.warning("Review invalid service metadata %s: %s", row, err)

    return list(consumers)


async def get_default_viewer(
    app: web.Application,
    file_type: str,
    file_size: int | None = None,
) -> ViewerInfo:
    """

    Raises:
        IncompatibleService
        FileToLarge
    """
    try:
        viewers = await list_viewers_info(app, file_type, only_default=True)
        viewer = viewers[0]
    except IndexError as err:
        raise IncompatibleService(file_type=file_type) from err

    if current_size := parse_obj_or_none(ByteSize, file_size):
        max_size: ByteSize = get_plugin_settings(app).STUDIES_MAX_FILE_SIZE_ALLOWED
        if current_size > max_size:
            raise FileToLarge(file_size_in_mb=current_size.to("MiB"))

    return viewer


@log_decorator(_logger, level=logging.DEBUG)
async def validate_requested_viewer(
    app: web.Application,
    file_type: str,
    file_size: int | None = None,
    service_key: str | None = None,
    service_version: str | None = None,
) -> ViewerInfo:
    """

    Raises:
        IncompatibleService: When there is no match

    """

    def _version(column_or_value):
        # converts version value string to array[integer] that can be compared
        return sa.func.string_to_array(column_or_value, ".").cast(ARRAY(INTEGER))

    if not service_key and not service_version:
        return await get_default_viewer(app, file_type, file_size)

    if service_key and service_version:
        async with get_database_engine(app).acquire() as conn:
            query = (
                services_consume_filetypes.select()
                .where(
                    (services_consume_filetypes.c.filetype == file_type)
                    & (services_consume_filetypes.c.service_key == service_key)
                    & (
                        _version(services_consume_filetypes.c.service_version)
                        <= _version(service_version)
                    )
                )
                .order_by(_version(services_consume_filetypes.c.service_version).desc())
                .limit(1)
            )

            result = await conn.execute(query)
            row = await result.first()
            if row:
                view = ViewerInfo.create_from_db(row)
                view.version = TypeAdapter(ServiceVersion).validate_python(
                    service_version
                )
                return view

    raise IncompatibleService(file_type=file_type)


@log_decorator(_logger, level=logging.DEBUG)
def validate_requested_file(
    app: web.Application, file_type: str, file_size: int | None = None
):
    # NOTE in the future we might want to prevent some types to be pulled
    assert file_type  # nosec

    if current_size := parse_obj_or_none(ByteSize, file_size):
        max_size: ByteSize = get_plugin_settings(app).STUDIES_MAX_FILE_SIZE_ALLOWED
        if current_size > max_size:
            raise FileToLarge(file_size_in_mb=current_size.to("MiB"))
