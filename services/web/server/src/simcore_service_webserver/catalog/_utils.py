import asyncio
import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.rest_responses import wrap_as_envelope
from servicelib.json_serialization import json_dumps
from yarl import URL

from ._constants import MSG_CATALOG_SERVICE_UNAVAILABLE

_logger = logging.getLogger(__name__)


@contextmanager
def handle_client_exceptions(app: web.Application) -> Iterator[ClientSession]:
    try:
        session: ClientSession = get_client_session(app)

        yield session

    except (asyncio.TimeoutError, ClientConnectionError, ClientResponseError) as err:
        _logger.debug("Request to catalog service failed: %s", err)
        raise web.HTTPServiceUnavailable(
            reason=MSG_CATALOG_SERVICE_UNAVAILABLE
        ) from err


async def make_request_and_envelope_response(
    app: web.Application,
    method: str,
    url: URL,
    headers: Mapping[str, str] | None = None,
    data: bytes | None = None,
) -> web.Response:
    """
    Helper to forward a request to the catalog service
    """
    with handle_client_exceptions(app) as session:

        async with session.request(method, url, headers=headers, data=data) as resp:
            payload = await resp.json()

            try:
                resp.raise_for_status()
                resp_data = wrap_as_envelope(data=payload)

            except ClientResponseError as err:
                if err.status >= 500:
                    raise err
                resp_data = wrap_as_envelope(error=payload["errors"])

            return web.json_response(resp_data, status=resp.status, dumps=json_dumps)
