from aiohttp import web
from aiohttp.typedefs import Handler
from aiohttp.web_request import Request
from pydantic import ValidationError
from servicelib.aiohttp.aiopg_utils import DBAPIError

from .constants import APP_DSM_KEY, DATCORE_STR
from .db_access_layer import InvalidFileIdentifier
from .db_tokens import get_api_token_and_secret
from .dsm import DataStorageManager
from .exceptions import FileMetaDataNotFoundError
from .models import DatCoreApiToken
from .utils import get_location_from_id


@web.middleware
async def dsm_exception_handler(
    request: Request, handler: Handler
) -> web.StreamResponse:
    try:
        return await handler(request)
    except InvalidFileIdentifier as err:
        raise web.HTTPUnprocessableEntity(
            reason=f"{err} is an invalid file identifier"
        ) from err
    except FileMetaDataNotFoundError as err:
        raise web.HTTPNotFound(reason=f"{err}") from err
    except ValidationError as err:
        raise web.HTTPUnprocessableEntity(reason=f"{err}") from err
    except DBAPIError as err:
        raise web.HTTPServiceUnavailable(
            reason="Unexpected error while accessing the database"
        ) from err


async def prepare_storage_manager(
    params: dict, query: dict, request: web.Request
) -> DataStorageManager:
    # FIXME: scope properly, either request or app level!!
    # Notice that every request is changing tokens!
    # I would rather store tokens in request instead of in dsm
    # or creating an different instance of dsm per request

    INIT_STR = "init"
    dsm: DataStorageManager = request.app[APP_DSM_KEY]
    user_id = query.get("user_id")
    location_id = params.get("location_id")
    location = (
        get_location_from_id(location_id) if location_id is not None else INIT_STR
    )

    if user_id and location in (INIT_STR, DATCORE_STR):
        # TODO: notify from db instead when tokens changed, then invalidate resource which enforces
        # re-query when needed.

        # updates from db
        token_info = await get_api_token_and_secret(request.app, int(user_id))
        if all(token_info):
            dsm.datcore_tokens[user_id] = DatCoreApiToken(*token_info)
        else:
            dsm.datcore_tokens.pop(user_id, None)
    return dsm
