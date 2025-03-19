from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from servicelib.fastapi.http_error import set_app_default_http_error_handlers
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
    error_content = {"errors": [f"{exc}"]}
    if exc.response["Error"]["Code"] == "NotAuthorizedException":
        return JSONResponse(
            content=jsonable_encoder({"error": error_content}),
            status_code=HTTP_401_UNAUTHORIZED,
        )
    return JSONResponse(
        content=jsonable_encoder({"error": error_content}),
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
    )


def set_exception_handlers(app: FastAPI) -> None:
    set_app_default_http_error_handlers(app)

    app.add_exception_handler(ClientError, botocore_exceptions_handler)
