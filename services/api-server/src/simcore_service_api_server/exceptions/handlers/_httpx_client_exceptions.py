""" General handling of httpx-based exceptions

    - httpx-based clients are used to communicate with other backend services
    - any exception raised by a httpx client will be handled here.
"""
import logging
from typing import Any

from fastapi import Request, status
from httpx import HTTPError, TimeoutException

from ._utils import create_error_json_response

_logger = logging.getLogger(__file__)


async def handle_httpx_client_exceptions(request: Request, exc: Exception):
    """
    Default httpx exception handler.
    See https://www.python-httpx.org/exceptions/
    With this in place only HTTPStatusErrors need to be customized closer to the httpx client itself.
    """
    assert request  # nosec
    assert isinstance(exc, HTTPError)

    status_code: Any
    detail: str
    headers: dict[str, str] = {}
    if isinstance(exc, TimeoutException):
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
        detail = f"Request to {exc.request.url.host.capitalize()} timed out"
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
        detail = f"{exc.request.url.host.capitalize()} service unexpectedly failed"

    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        _logger.exception("%s. host=%s. %s", detail, exc.request.url.host, f"{exc}")

    return create_error_json_response(
        f"{detail}", status_code=status_code, headers=headers
    )
