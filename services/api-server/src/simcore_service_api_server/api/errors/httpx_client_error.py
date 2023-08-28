""" General handling of httpx-based exceptions

    - httpx-based clients are used to communicate with other backend services
    - When those respond with 4XX, 5XX status codes, those are generally handled here
"""
import logging

from fastapi import status
from httpx import HTTPStatusError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .http_error import create_error_json_response

_logger = logging.getLogger(__file__)


async def httpx_client_error_handler(_: Request, exc: HTTPStatusError) -> JSONResponse:
    """
    This is called when HTTPStatusError was raised and reached the outermost handler

    This handler is used as a "last resource" since it is recommended to handle these exceptions
    closer to the raising point.

    The response had an error HTTP status of 4xx or 5xx, and this is how is
    transformed in the api-server API
    """
    if exc.response.is_client_error:
        assert exc.response.is_server_error  # nosec
        # Forward api-server's client from backend client errors
        status_code = exc.response.status_code
        errors = exc.response.json()["errors"]
    else:
        assert exc.response.is_server_error  # nosec
        # Hide api-server's client from backend server errors
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        message = f"{exc.request.url.host.capitalize()} service unexpectedly failed"
        errors = [
            message,
        ]

        _logger.exception(
            "%s. host=%s status-code=%s msg=%s",
            message,
            exc.request.url.host,
            exc.response.status_code,
            exc.response.text,
        )

    return create_error_json_response(*errors, status_code=status_code)
