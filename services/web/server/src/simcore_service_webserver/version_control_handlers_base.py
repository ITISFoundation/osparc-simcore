import logging
from functools import wraps

from aiohttp import web
from pydantic.error_wrappers import ValidationError
from servicelib.aiohttp.typing_extension import Handler
from servicelib.json_serialization import json_dumps

from .projects.projects_exceptions import ProjectNotFoundError
from .version_control_errors import InvalidParameterError, NoCommitError, NotFoundError

logger = logging.getLogger(__name__)


def handle_request_errors(handler: Handler) -> Handler:
    """
    - required and type validation of path and query parameters
    """

    @wraps(handler)
    async def wrapped(request: web.Request):
        try:
            resp = await handler(request)
            return resp

        except KeyError as err:
            # NOTE: handles required request.match_info[*] or request.query[*]
            logger.debug(err, exc_info=True)
            raise web.HTTPBadRequest(reason=f"Expected parameter {err}") from err

        except ValidationError as err:
            #  NOTE: pydantic.validate_arguments parses and validates -> ValidationError
            logger.debug(err, exc_info=True)
            raise web.HTTPUnprocessableEntity(
                text=json_dumps({"error": err.errors()}),
                content_type="application/json",
            ) from err

        except (InvalidParameterError, NoCommitError) as err:
            raise web.HTTPUnprocessableEntity(reason=str(err)) from err

        except NotFoundError as err:
            raise web.HTTPNotFound(reason=str(err)) from err

        except ProjectNotFoundError as err:
            logger.debug(err, exc_info=True)
            raise web.HTTPNotFound(
                reason=f"Project not found {err.project_uuid} or not accessible. Skipping snapshot"
            ) from err

    return wrapped


# FIXME: access rights using same approach as in access_layer.py in storage.
# A user can only check snapshots (subresource) of its project (parent resource)
