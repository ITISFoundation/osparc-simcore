""" Core functionality to interact with the director-v2 service

director-v2 rest API common functionality includes

- common types and constants
- requests helper function to call the API
- thin API client wrapper instance associated to the app's lifespan

"""

import asyncio
import logging
from typing import Any, Optional, Union

import aiohttp
from aiohttp import ClientTimeout, web
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random
from yarl import URL

from .director_v2_exceptions import DirectorServiceError
from .director_v2_settings import get_client_session

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


async def request_director_v2(
    app: web.Application,
    method: str,
    url: URL,
    expected_status: type[web.HTTPSuccessful] = web.HTTPOk,
    headers: Optional[dict[str, str]] = None,
    data: Optional[Any] = None,
    on_error: Optional[
        dict[int, tuple[type[DirectorServiceError], dict[str, Any]]]
    ] = None,
    **kwargs,
) -> DataBody:
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
                    )

                    if response.status != expected_status.status_code:
                        if response.status in on_error:
                            exc, exc_ctx = on_error[response.status]
                            raise exc(
                                **exc_ctx, status=response.status, reason=f"{payload}"
                            )
                        raise DirectorServiceError(
                            status=response.status, reason=f"{payload}", url=url
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
    log.error("Unexpected result calling %s, %s", f"{url=}", f"{method=}")
    raise DirectorServiceError(
        status=web.HTTPClientError.status_code,
        reason="Unexpected client error",
        url=url,
    )
