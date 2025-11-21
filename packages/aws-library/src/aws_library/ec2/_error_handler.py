import functools
import logging
import re
from collections.abc import Callable, Coroutine
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    Final,
    ParamSpec,
    TypeVar,
    cast,
)

from botocore import exceptions as botocore_exc

from ._errors import (
    EC2AccessError,
    EC2InstanceNotFoundError,
    EC2InstanceTypeInvalidError,
    EC2InsufficientCapacityError,
    EC2NotConnectedError,
    EC2RuntimeError,
    EC2TimeoutError,
)

if TYPE_CHECKING:
    # NOTE: TYPE_CHECKING is True when static type checkers are running,
    # allowing for circular imports only for them (mypy, pylance, ruff)
    from ._client import SimcoreEC2API


P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")
Self = TypeVar("Self", bound="SimcoreEC2API")


_INSUFFICIENT_CAPACITY_ERROR_MSG_PATTERN: Final[re.Pattern] = re.compile(
    r"sufficient (?P<instance_type>\S+) capacity in the Availability Zone you requested "
    r"\((?P<failed_az>\S+)\)"
)


def _map_botocore_client_exception(
    botocore_error: botocore_exc.ClientError,
    *args,  # pylint: disable=unused-argument # noqa: ARG001
    **kwargs,  # pylint: disable=unused-argument # noqa: ARG001
) -> EC2AccessError:
    # see https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html#parsing-error-responses-and-catching-exceptions-from-aws-services
    status_code = cast(
        int,
        botocore_error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", "-1"),
    )
    error_code = botocore_error.response.get("Error", {}).get("Code", "Unknown")
    error_msg = botocore_error.response.get("Error", {}).get("Message", "Unknown")
    operation_name = botocore_error.operation_name
    match error_code:
        case "InvalidInstanceID.NotFound":
            return EC2InstanceNotFoundError()
        case "InvalidInstanceType":
            return EC2InstanceTypeInvalidError()
        case "InsufficientInstanceCapacity":
            availability_zone = "unknown"
            instance_type = "unknown"
            if match := re.search(_INSUFFICIENT_CAPACITY_ERROR_MSG_PATTERN, error_msg):
                instance_type = match.group("instance_type")
                availability_zone = match.group("failed_az")

            raise EC2InsufficientCapacityError(
                availability_zones=availability_zone, instance_type=instance_type
            )
        case _:
            return EC2AccessError(
                status_code=status_code,
                operation_name=operation_name,
                code=error_code,
                error=error_msg,
            )


def ec2_exception_handler(
    logger: logging.Logger,
) -> Callable[
    [Callable[Concatenate[Self, P], Coroutine[Any, Any, R]]],
    Callable[Concatenate[Self, P], Coroutine[Any, Any, R]],
]:
    def decorator(
        func: Callable[Concatenate[Self, P], Coroutine[Any, Any, R]],
    ) -> Callable[Concatenate[Self, P], Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(self: Self, *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await func(self, *args, **kwargs)
            except botocore_exc.ClientError as exc:
                raise _map_botocore_client_exception(exc, *args, **kwargs) from exc
            except botocore_exc.WaiterError as exc:
                raise EC2TimeoutError(details=f"{exc}") from exc
            except botocore_exc.EndpointConnectionError as exc:
                raise EC2NotConnectedError from exc
            except botocore_exc.BotoCoreError as exc:
                logger.exception("Unexpected error in EC2 client: ")
                raise EC2RuntimeError from exc

        wrapper.__doc__ = f"{func.__doc__}\n\n{ec2_exception_handler.__doc__}"

        return wrapper

    return decorator
