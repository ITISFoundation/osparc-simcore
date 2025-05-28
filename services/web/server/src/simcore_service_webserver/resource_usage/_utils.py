import logging
from collections.abc import Iterator
from contextlib import contextmanager

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from servicelib.aiohttp import status
from servicelib.aiohttp.client_session import get_client_session

from ._constants import (
    MSG_RESOURCE_USAGE_TRACKER_NOT_FOUND,
    MSG_RESOURCE_USAGE_TRACKER_SERVICE_UNAVAILABLE,
)

_logger = logging.getLogger(__name__)


@contextmanager
def handle_client_exceptions(app: web.Application) -> Iterator[ClientSession]:
    try:
        session: ClientSession = get_client_session(app)

        yield session
    except ClientResponseError as err:
        if err.status == status.HTTP_404_NOT_FOUND:
            raise web.HTTPNotFound(text=MSG_RESOURCE_USAGE_TRACKER_NOT_FOUND)
        raise web.HTTPServiceUnavailable(
            reason=MSG_RESOURCE_USAGE_TRACKER_SERVICE_UNAVAILABLE
        ) from err

    except (TimeoutError, ClientConnectionError) as err:
        _logger.debug("Request to resource usage tracker service failed: %s", err)
        raise web.HTTPServiceUnavailable(
            reason=MSG_RESOURCE_USAGE_TRACKER_SERVICE_UNAVAILABLE
        ) from err
