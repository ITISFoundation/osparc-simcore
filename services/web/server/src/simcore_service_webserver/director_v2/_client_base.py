import logging
from typing import Any, TypeAlias

import aiohttp
from aiohttp import ClientSession, ClientTimeout, web
from servicelib.aiohttp import status
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random
from yarl import URL

from .exceptions import DirectorV2ServiceError
from .settings import get_client_session

log = logging.getLogger(__name__)


SERVICE_HEALTH_CHECK_TIMEOUT = ClientTimeout(total=2, connect=1)

DEFAULT_RETRY_POLICY: dict[str, Any] = {
    "wait": wait_random(0, 1),
    "stop": stop_after_attempt(2),
    "reraise": True,
    "before_sleep": before_sleep_log(log, logging.WARNING),
}


DataType: TypeAlias = dict[str, Any]
DataBody: TypeAlias = DataType | list[DataType] | None


_StatusToExceptionMapping = dict[
    int, tuple[type[DirectorV2ServiceError], dict[str, Any]]
]


def _get_exception_from(
    status_code: int, on_error: _StatusToExceptionMapping | None, details: str, url: URL
):
    if on_error and status_code in on_error:
        exc_cls, exc_ctx = on_error[status_code]
        return exc_cls(**exc_ctx, status=status_code, details=details)

    # default
    return DirectorV2ServiceError(status=status_code, details=details, url=url)


@retry(**DEFAULT_RETRY_POLICY)
async def _make_request(
    session: ClientSession,
    method: str,
    headers: dict[str, str] | None,
    data: Any | None,
    expected_status: type[web.HTTPSuccessful],
    on_error: _StatusToExceptionMapping | None,
    url: URL,
    **kwargs,
) -> DataBody | str:
    async with session.request(
        method, url, headers=headers, json=data, **kwargs
    ) as response:
        payload: dict[str, Any] | list[dict[str, Any]] | None | str = (
            await response.json()
            if response.content_type == MIMETYPE_APPLICATION_JSON
            else await response.text()
        )

        if response.status != expected_status.status_code:
            raise _get_exception_from(
                response.status, on_error, details=f"{payload}", url=url
            )
        return payload


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
    session = get_client_session(app)
    on_error = on_error or {}

    try:
        payload: DataBody | str = await _make_request(
            session, method, headers, data, expected_status, on_error, url, **kwargs
        )
        return payload

    except TimeoutError as err:
        raise DirectorV2ServiceError(
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=f"request to director-v2 timed-out: {err}",
            url=url,
        ) from err

    except aiohttp.ClientError as err:
        raise DirectorV2ServiceError(
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=f"request to director-v2 service unexpected error {err}",
            url=url,
        ) from err
