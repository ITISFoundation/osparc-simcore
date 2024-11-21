import logging
from functools import wraps
from typing import Any

from aiohttp import web
from common_library.json_serialization import json_dumps
from pydantic import ValidationError
from servicelib.aiohttp.typing_extension import Handler

from ..projects.exceptions import ProjectNotFoundError
from .errors import InvalidParameterError, NoCommitError, NotFoundError

_logger = logging.getLogger(__name__)


def handle_request_errors(handler: Handler) -> Handler:
    """
    - required and type validation of path and query parameters
    """

    @wraps(handler)
    async def wrapped(request: web.Request):
        try:
            response: Any = await handler(request)
            return response

        except KeyError as err:
            # NOTE: handles required request.match_info[*] or request.query[*]
            _logger.debug(err, exc_info=True)
            raise web.HTTPBadRequest(reason=f"Expected parameter {err}") from err

        except ValidationError as err:
            #  NOTE: pydantic.validate_arguments parses and validates -> ValidationError
            _logger.debug(err, exc_info=True)
            raise web.HTTPUnprocessableEntity(
                text=json_dumps({"error": err.errors()}),
                content_type="application/json",
            ) from err

        except (InvalidParameterError, NoCommitError) as err:
            raise web.HTTPUnprocessableEntity(reason=str(err)) from err

        except NotFoundError as err:
            raise web.HTTPNotFound(reason=str(err)) from err

        except ProjectNotFoundError as err:
            _logger.debug(err, exc_info=True)
            raise web.HTTPNotFound(
                reason=f"Project not found {err.project_uuid} or not accessible. Skipping snapshot"
            ) from err

    return wrapped
