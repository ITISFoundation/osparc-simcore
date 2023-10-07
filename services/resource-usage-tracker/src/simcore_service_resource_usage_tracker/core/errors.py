from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic.errors import PydanticErrorMixin


class ResourceUsageTrackerRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Resource-usage-tracker unexpected error"


class ConfigurationError(ResourceUsageTrackerRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class MyHTTPException(HTTPException):
    pass


def my_http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:  # pylint: disable=unused-argument
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})
