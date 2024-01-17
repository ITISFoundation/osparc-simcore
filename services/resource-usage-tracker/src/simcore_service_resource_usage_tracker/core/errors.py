from fastapi import Request
from fastapi.responses import JSONResponse
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CustomResourceUsageTrackerError,
    ResourceUsageTrackerRuntimeError,
)


class ConfigurationError(ResourceUsageTrackerRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


def http404_error_handler(
    request: Request,  # pylint: disable=unused-argument
    error: CustomResourceUsageTrackerError,
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"message": f"{error.msg_template}"})
