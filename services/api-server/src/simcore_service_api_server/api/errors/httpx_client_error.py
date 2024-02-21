""" General handling of httpx-based exceptions

    - httpx-based clients are used to communicate with other backend services
    - any exception raised by a httpx client will be handled here.
"""
import logging
from functools import partial
from inspect import iscoroutinefunction
from typing import Any

from fastapi import HTTPException, status
from httpx import HTTPError, HTTPStatusError, TimeoutException

_logger = logging.getLogger(__file__)


def httpx_exception_handler(cls):
    class Wrapper(cls):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def __getattribute__(self, name):
            attr = super().__getattribute__(name)
            if iscoroutinefunction(attr):
                return partial(self._method, attr)
            else:
                return attr

        async def _method(self, method, *args, **kwargs):
            try:
                result = await method(*args, **kwargs)
            except HTTPError as exc:
                await _handle_httpx_client_exception(exc)
            return result

    return Wrapper


async def _handle_httpx_client_exception(exc: HTTPError):
    """See https://www.python-httpx.org/exceptions/"""
    status_code: Any
    detail: str
    headers: dict[str, str] = {}
    if isinstance(exc, HTTPStatusError):
        status_code, detail, headers = await _handle_httpx_status_exceptions(exc)
    elif isinstance(exc, TimeoutException):
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
        detail = f"Request to {exc.request.url.host.capitalize()} timed out"
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
        detail = f"{exc.request.url.host.capitalize()} service unexpectedly failed"

    _logger.exception(
        "%s. host=%s",
        detail,
        exc.request.url.host,
    )
    raise HTTPException(
        status_code=status_code, detail=detail, headers=headers
    ) from exc


async def _handle_httpx_status_exceptions(
    exc: HTTPStatusError,
) -> tuple[int, str, dict[str, str]]:
    status_code: int
    detail: str
    headers: dict[str, str] = {}
    response_status = exc.response.status_code
    error_msg = exc.response.json()["errors"].join(", ")
    if response_status in {
        status.HTTP_402_PAYMENT_REQUIRED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_410_GONE,
        status.HTTP_429_TOO_MANY_REQUESTS,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    }:  # status codes mapped directly back to user
        status_code = response_status
        if "Retry-After" in exc.response.headers:
            headers["Retry-After"] = exc.response.headers["Retry-After"]
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    detail = f"{exc.request.url.host.capitalize()} encountered an issue: {error_msg}"
    return status_code, detail, headers
