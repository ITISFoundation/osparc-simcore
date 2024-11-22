from botocore.exceptions import ClientError
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_500_INTERNAL_SERVER_ERROR


async def botocore_exceptions_handler(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, ClientError)  # nosec
    assert "Error" in exc.response  # nosec
    assert "Code" in exc.response["Error"]  # nosec
    if exc.response["Error"]["Code"] == "NotAuthorizedException":
        return JSONResponse(
            content=jsonable_encoder({"errors": exc.response["Error"]}),
            status_code=HTTP_401_UNAUTHORIZED,
        )
    return JSONResponse(
        content=jsonable_encoder({"errors": exc.response["Error"]}),
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
    )
