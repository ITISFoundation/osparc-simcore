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
        detail = exc.response.text

    else:
        # Hide api-server client from backend server errors
        assert exc.response.status_code >= 500  # nosec
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = [
            "Some backend service is unexpectedly failing",
        ]
        log.exception("Some backend service responded with a server error 5XX")

    return JSONResponse(
        content=jsonable_encoder({"errors": [detail]}), status_code=status_code
    )
