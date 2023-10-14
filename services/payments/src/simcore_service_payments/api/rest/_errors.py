import http

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ...models.schemas.errors import DefaultApiError


async def http_exception_as_json_response(
    request: Request, exc: HTTPException
) -> JSONResponse:
    assert request
    status_code = http.HTTPStatus(exc.status_code)

    assert (  # nosec
        status_code.phrase == exc.detail
    )  # defined in starlette.exceptions.HTTPException

    error = DefaultApiError(
        name=status_code.phrase,
        message=status_code.description,
        detail=f"{exc.status_code}-{exc.detail}",
    )
    return JSONResponse(jsonable_encoder(error), status_code=exc.status_code)
