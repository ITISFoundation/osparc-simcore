""" Core functionality to interact with the director-v2 service

director-v2 rest API common functionality includes

- common types and constants
- requests helper function to call the API
- thin API client wrapper instance associated to the app's lifespan

"""

import asyncio
import logging
from typing import Any, Union

import aiohttp
from aiohttp import ClientTimeout, web
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random
from yarl import URL

from .exceptions import DirectorServiceError
from .settings import get_client_session

log = logging.getLogger(__name__)


SERVICE_HEALTH_CHECK_TIMEOUT = ClientTimeout(total=2, connect=1)  # type:ignore

DEFAULT_RETRY_POLICY = dict(
    wait=wait_random(0, 1),
    stop=stop_after_attempt(2),
    reraise=True,
    before_sleep=before_sleep_log(log, logging.WARNING),
)


DataType = dict[str, Any]
DataBody = Union[DataType, list[DataType], None]


_StatusToExceptionMapping = dict[int, tuple[type[DirectorServiceError], dict[str, Any]]]


def _get_exception_from(
    status_code: int, on_error: _StatusToExceptionMapping, reason: str, url: URL
):
    if status_code in on_error:
        exc, exc_ctx = on_error[status_code]
        return exc(**exc_ctx, status=status_code, reason=reason)
    # default
    return DirectorServiceError(status=status_code, reason=reason, url=url)


async def request_director_v2(
    app: web.Application,
    method: str,
    url: URL,
    *,
    expected_status: type[web.HTTPSuccessful] = web.HTTPOk,
    headers: dict[str, str] | None = None,
    data: Any | None = None,
    on_error: _StatusToExceptionMapping | None = None,
    **kwargs,
) -> DataBody | str:
    """
    helper to make requests to director-v2 API
    SEE OAS in services/director-v2/openapi.json
    """
    # TODO: deprecate!
    session = get_client_session(app)
    on_error = on_error or {}

    try:
        async for attempt in AsyncRetrying(**DEFAULT_RETRY_POLICY):
            with attempt:

                async with session.request(
                    method, url, headers=headers, json=data, **kwargs
                ) as response:
                    payload = (
                        await response.json()
                        if response.content_type == "application/json"
                        else await response.text()
                        # FIXME: text should never happen ... perhaps unhandled exception!
                    )

                    if response.status != expected_status.status_code:
                        raise _get_exception_from(
                            response.status, on_error, reason=f"{payload}", url=url
                        )
                    return payload

    # TODO: enrich with https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
    except asyncio.TimeoutError as err:
        raise DirectorServiceError(
            status=web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 timed-out: {err}",
            url=url,
        ) from err

    except aiohttp.ClientError as err:
        raise DirectorServiceError(
            status=web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 service unexpected error {err}",
            url=url,
        ) from err
