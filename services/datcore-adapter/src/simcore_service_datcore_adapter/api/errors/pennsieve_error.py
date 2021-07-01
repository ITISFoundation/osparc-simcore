from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_500_INTERNAL_SERVER_ERROR

from botocore.exceptions import ClientError


async def botocore_exceptions_handler(
    _: Request,
    exc: ClientError,
) -> JSONResponse:
    if exc.response["Error"]["Code"] == "NotAuthorizedException":
        return JSONResponse(
            content=jsonable_encoder({"errors": exc.response["Error"]}),
            status_code=HTTP_401_UNAUTHORIZED,
        )
    return JSONResponse(
        content=jsonable_encoder({"errors": exc.response["Error"]}),
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
    )
