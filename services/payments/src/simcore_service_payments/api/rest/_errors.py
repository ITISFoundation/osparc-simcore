from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ...models.schemas.errors import DefaultApiError


async def http_exception_as_json_response(
    request: Request, exc: HTTPException
) -> JSONResponse:
    assert request  # nosec
    error = DefaultApiError.from_status_code(exc.status_code)

    error_detail = error.detail or ""
    if exc.detail not in error_detail:
        # starlette.exceptions.HTTPException default to similar detail
        error.detail = exc.detail

    return JSONResponse(
        jsonable_encoder(error, exclude_none=True), status_code=exc.status_code
    )


async def handle_errors_as_500(request: Request, exc: HTTPException) -> JSONResponse:
    assert request  # nosec
    error = DefaultApiError.from_status_code(status.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(
        jsonable_encoder(error, exclude_none=True), status_code=exc.status_code
    )
