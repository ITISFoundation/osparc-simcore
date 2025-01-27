from fastapi.encoders import jsonable_encoder
from fastapi.openapi.constants import REF_PREFIX
from fastapi.openapi.utils import validation_error_response_definition
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY


async def http422_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert hasattr(exc, "errors")  # nosec
    return JSONResponse(
        content=jsonable_encoder({"errors": exc.errors()}),
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
    )


validation_error_response_definition["properties"] = {
    "errors": {
        "title": "Validation errors",
        "type": "array",
        "items": {"$ref": f"{REF_PREFIX}ValidationError"},
    },
}
