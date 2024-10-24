from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.constants import REF_PREFIX
from fastapi.openapi.utils import validation_error_response_definition
from pydantic import ValidationError
from starlette.responses import JSONResponse

from ._utils import create_error_json_response


async def http422_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, RequestValidationError | ValidationError)

    return create_error_json_response(
        *exc.errors(), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


validation_error_response_definition["properties"] = {
    "errors": {
        "title": "Validation errors",
        "type": "array",
        "items": {"$ref": f"{REF_PREFIX}ValidationError"},
    },
}
