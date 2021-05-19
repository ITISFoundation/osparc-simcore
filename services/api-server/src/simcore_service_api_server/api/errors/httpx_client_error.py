""" General handling of httpx-based exceptions

    - httpx-based clients are used to communicate with other backend services
    - When those respond with 4XX, 5XX status codes, those are generally handled here
"""
import logging

from fastapi import status
from fastapi.encoders import jsonable_encoder
from httpx import HTTPStatusError
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger(__file__)


async def httpx_client_error_handler(_: Request, exc: HTTPStatusError) -> JSONResponse:
    """
    This is called when HTTPStatusError was raised and reached tha outermost handler

    The response had an error HTTP status of 4xx or 5xx, and this is how is
    transformed in the api-server API
    """
    if 400 <= exc.response.status_code < 500:
        # Forward backend client errors
        status_code = exc.response.status_code
        errors = exc.response.json()["errors"]

    else:
        # Hide api-server client from backend server errors
        assert exc.response.status_code >= 500  # nosec
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        message = f"{exc.request.url.host.capitalize()} service unexpectedly failed"
        log.exception(
            "%s. host=%s status-code=%s msg=%s",
            message,
            exc.request.url.host,
            exc.response.status_code,
            exc.response.text,
        )
        errors = [
            message,
        ]

    return JSONResponse(
        content=jsonable_encoder({"errors": errors}), status_code=status_code
    )
