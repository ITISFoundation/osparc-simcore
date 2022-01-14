import logging
import uuid
from collections import deque
from functools import lru_cache
from typing import List, Optional

from aiohttp import web
from aiopg.sa.result import RowProxy
from models_library.services import KEY_RE, VERSION_RE
from pydantic import BaseModel, Field, ValidationError, constr
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)

from .._constants import APP_DB_ENGINE_KEY

MEGABYTES = 1024 * 1024

log = logging.getLogger(__name__)


# VIEWERS  -----------------------------------------------------------------------------
class StudyDispatcherError(Exception):
    def __init__(self, reason):
        super().__init__()
        self.reason = reason


class ViewerInfo(BaseModel):
    """Here a viewer denotes a service
      - that supports (i.e. can consume) a specific filetype and
      - that is available to everyone
    and therefore it can be dispatched to both guest and active users
    to visualize a file of that type
    """

    key: constr(regex=KEY_RE)  # type: ignore
    version: constr(regex=VERSION_RE)  # type: ignore
    filetype: str = Field(..., description="Filetype associated to this viewer")

    label: str = Field(..., description="Display name")
    input_port_key: str = Field(
        description="Name of the connection port, since it is service-dependent",
    )
    is_guest_allowed: bool = True

    @property
    def footprint(self) -> str:
        return f"{self.key}:{self.version}"

    @property
    def title(self) -> str:
        """human readable title"""
        return f"{self.label.capitalize()} v{self.version}"

    @classmethod
    def create_from_db(cls, row: RowProxy) -> "ViewerInfo":
        return cls(
            key=row["service_key"],
            version=row["service_version"],
            filetype=row["filetype"],
            label=row["service_display_name"] or row["service_key"].split("/")[-1],
            input_port_key=row["service_input_port"],
            is_guest_allowed=row["is_guest_allowed"],
        )


async def list_viewers_info(
    app: web.Application, file_type: Optional[str] = None, *, only_default: bool = False
) -> List[ViewerInfo]:
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

        log.debug("Listing viewers:\n%s", stmt)

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
                log.warning("Review invalid service metadata %s: %s", row, err)

    return list(consumers)


async def get_default_viewer(
    app: web.Application,
    file_type: str,
    file_size: Optional[int] = None,
) -> ViewerInfo:
    try:
        viewers = await list_viewers_info(app, file_type, only_default=True)
        viewer = viewers[0]
    except IndexError as err:
        raise StudyDispatcherError(
            f"No viewer available for file type '{file_type}'"
        ) from err

    # TODO: This is a temporary limitation just for demo purposes.
    if file_size is not None and file_size > 50 * MEGABYTES:
        raise StudyDispatcherError(
            f"File size {file_size*1E-6} MB is over allowed limit"
        )

    return viewer


async def validate_requested_viewer(
    app: web.Application,
    file_type: str,
    file_size: Optional[int] = None,
    service_key: Optional[str] = None,
    service_version: Optional[str] = None,
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


# UTILITIES ---------------------------------------------------------------
BASE_UUID = uuid.UUID("ca2144da-eabb-4daf-a1df-a3682050e25f")


@lru_cache()
def compose_uuid_from(*values) -> str:
    composition = "/".join(map(str, values))
    new_uuid = uuid.uuid5(BASE_UUID, composition)
    return str(new_uuid)
