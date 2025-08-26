import functools
import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar

from botocore import exceptions as botocore_exc

from ._errors import (
    EC2AccessError,
    EC2InstanceNotFoundError,
    EC2InstanceTypeInvalidError,
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


def _map_botocore_client_exception(
    botocore_error: botocore_exc.ClientError,
    *args,  # pylint: disable=unused-argument # noqa: ARG001
    **kwargs,  # pylint: disable=unused-argument # noqa: ARG001
) -> EC2AccessError:
    status_code = int(
        botocore_error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        or botocore_error.response.get("Error", {}).get("Code", -1)
    )
    operation_name = botocore_error.operation_name
    match status_code, operation_name:
        case 400, "StartInstances":
            return EC2InstanceNotFoundError()
        case 400, "StopInstances":
            return EC2InstanceNotFoundError()
        case 400, "TerminateInstances":
            return EC2InstanceNotFoundError()
        case 400, "DescribeInstanceTypes":
            return EC2InstanceTypeInvalidError()
        case _:
            return EC2AccessError(
                operation_name=operation_name,
                code=status_code,
                error=f"{botocore_error}",
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
