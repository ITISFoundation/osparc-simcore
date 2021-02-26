import logging
import uuid
from collections import deque
from functools import lru_cache
from typing import List, Optional

from aiohttp import web
from models_library.services import KEY_RE, VERSION_RE
from pydantic import BaseModel, Field, ValidationError, constr
from simcore_postgres_database.webserver_models import services_consume_filetypes

from ..constants import APP_DB_ENGINE_KEY

MEGABYTES = 1024 * 1024

log = logging.getLogger(__name__)


# VIEWERS  -----------------------------------------------------------------------------
class MatchNotFoundError(Exception):
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

    key: constr(regex=KEY_RE)
    version: constr(regex=VERSION_RE)
    filetype: str = Field(..., description="Filetype associated to this viewer")

    label: str = Field(..., description="Display name")
    input_port_key: str = Field(
        "input_1",
        description="Name of the connection port, since it is service-dependent",
    )

    @property
    def footprint(self) -> str:
        return f"{self.key}:{self.version}"

    @property
    def title(self) -> str:
        """ human readable title """
        return f"{self.label.capitalize()} v{self.version}"


async def list_viewers(
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
            stmt.where(services_consume_filetypes.c.filetype == file_type)

        stmt.order_by("preference_order")

        if only_default:
            stmt.limit(1)

        log.debug("Listing viewers: %s", stmt)

        async for row in await conn.execute(stmt):
            try:
                display_name = (
                    row["service_display_name"] or row["service_key"].split("/")[-1]
                )

                consumer = ViewerInfo(
                    key=row["service_key"],
                    version=row["service_version"],
                    label=display_name,
                    input_port_key=row["service_input_port"],
                )
                consumers.append(consumer)

            except ValidationError as err:
                log.warning("Review invalid service metadata %s: %s", row, err)

    return list(consumers)


async def find_compatible_viewer(
    app: web.Application,
    file_type: str,
    file_size: Optional[int] = None,
) -> ViewerInfo:
    try:
        viewers = await list_viewers(app, file_type, only_default=True)
        viewer = viewers[0]
    except KeyError as err:
        raise MatchNotFoundError(
            f"No viewer available for file type '{file_type}''"
        ) from err

    # TODO: This is a temporary limitation just for demo purposes.
    if file_size is not None and file_size > 50 * MEGABYTES:
        raise MatchNotFoundError(f"File size {file_size*1E-6} MB is over allowed limit")

    return viewer


# UTILITIES ---------------------------------------------------------------
BASE_UUID = uuid.UUID("ca2144da-eabb-4daf-a1df-a3682050e25f")


@lru_cache()
def compose_uuid_from(*values) -> str:
    composition = "/".join(map(str, values))
    new_uuid = uuid.uuid5(BASE_UUID, composition)
    return str(new_uuid)


class ValidationMixin:
    @classmethod
    def from_request(cls, request: web.Request):
        try:
            obj = cls(**dict(request.query))
        except ValidationError as err:

            raise web.HTTPBadRequest(
                content_type="application/json",
                body=err.json(),
                reason=f"{len(err.errors())} invalid parameters in query",
            )
        else:
            return obj
