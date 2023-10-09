from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic.errors import PydanticErrorMixin


class ResourceUsageTrackerRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Resource-usage-tracker unexpected error"


class ConfigurationError(ResourceUsageTrackerRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class CustomResourceUsageTrackerRuntimeError(ResourceUsageTrackerRuntimeError):
    msg_template: str = "{msg}"


def http404_error_handler(
    request: Request,
    error: CustomResourceUsageTrackerRuntimeError,  # pylint: disable=unused-argument
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"message": error.msg_template})
