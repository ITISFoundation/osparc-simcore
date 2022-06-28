from aiohttp import web
from aiohttp.typedefs import Handler
from aiohttp.web_request import Request
from pydantic import ValidationError
from servicelib.aiohttp.aiopg_utils import DBAPIError

from .db_access_layer import InvalidFileIdentifier
from .exceptions import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
    LinkAlreadyExistsError,
    S3KeyNotFoundError,
)


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
    except (FileMetaDataNotFoundError, S3KeyNotFoundError) as err:
        raise web.HTTPNotFound(reason=f"{err}") from err
    except FileAccessRightError as err:
        raise web.HTTPForbidden(reason=f"{err}") from err
    except LinkAlreadyExistsError as err:
        raise web.HTTPUnprocessableEntity(reason=f"{err}") from err
    except ValidationError as err:
        raise web.HTTPUnprocessableEntity(reason=f"{err}") from err
    except DBAPIError as err:
        raise web.HTTPServiceUnavailable(
            reason="Unexpected error while accessing the database"
        ) from err
