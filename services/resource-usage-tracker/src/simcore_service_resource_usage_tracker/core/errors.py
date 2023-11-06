from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic.errors import PydanticErrorMixin


class ResourceUsageTrackerRuntimeError(PydanticErrorMixin, RuntimeError):
    msg: str = "Resource-usage-tracker unexpected error"


class ConfigurationError(ResourceUsageTrackerRuntimeError):
    msg: str = "Application misconfiguration"


class CustomResourceUsageTrackerError(ResourceUsageTrackerRuntimeError):
    msg: str


def http404_error_handler(
    request: Request,  # pylint: disable=unused-argument
    error: CustomResourceUsageTrackerError,
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"message": error.msg})
