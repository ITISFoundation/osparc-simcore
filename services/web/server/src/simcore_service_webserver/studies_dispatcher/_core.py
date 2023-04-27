import logging
import uuid
from collections import deque
from functools import lru_cache

from aiohttp import web
from pydantic import ValidationError
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)

from .._constants import APP_DB_ENGINE_KEY
from ._errors import StudyDispatcherError
from ._models import ViewerInfo

_MEGABYTES = 1024 * 1024
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
    consumers = deque()

    async with app[APP_DB_ENGINE_KEY].acquire() as conn:

        # FIXME: ADD CONDITION: service MUST be shared with EVERYBODY!
        stmt = services_consume_filetypes.select()
        if file_type:
            stmt = stmt.where(services_consume_filetypes.c.filetype == file_type)

        stmt = stmt.order_by("filetype", "preference_order")

        if file_type and only_default:
            stmt = stmt.limit(1)

        _logger.debug("Listing viewers:\n%s", stmt)

        listed_filetype = set()
        async for row in await conn.execute(stmt):
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
    try:
        viewers = await list_viewers_info(app, file_type, only_default=True)
        viewer = viewers[0]
    except IndexError as err:
        raise StudyDispatcherError(
            f"No viewer available for file type '{file_type}'"
        ) from err

    # TODO: This is a temporary limitation just for demo purposes.
    if file_size is not None and file_size > 50 * _MEGABYTES:
        raise StudyDispatcherError(
            f"File size {file_size*1E-6} MB is over allowed limit"
        )

    return viewer


@log_decorator(_logger, level=logging.DEBUG)
async def validate_requested_viewer(
    app: web.Application,
    file_type: str,
    file_size: int | None = None,
    service_key: str | None = None,
    service_version: str | None = None,
) -> ViewerInfo:

    if not service_key and not service_version:
        return await get_default_viewer(app, file_type, file_size)

    if service_key and service_version:
        async with app[APP_DB_ENGINE_KEY].acquire() as conn:
            stmt = services_consume_filetypes.select().where(
                (services_consume_filetypes.c.filetype == file_type)
                & (services_consume_filetypes.c.service_key == service_key)
                & (services_consume_filetypes.c.service_version == service_version)
            )
            result = await conn.execute(stmt)
            row = await result.first()
            if row:
                return ViewerInfo.create_from_db(row)

    raise StudyDispatcherError(
        f"None of the registered viewers can open file type '{file_type}'"
    )
