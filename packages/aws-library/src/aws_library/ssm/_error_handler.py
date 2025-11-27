import functools
import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar

from botocore import exceptions as botocore_exc

from ._errors import (
    SSMAccessError,
    SSMInvalidCommandError,
    SSMNotConnectedError,
    SSMRuntimeError,
    SSMSendCommandInstancesNotReadyError,
    SSMTimeoutError,
)

if TYPE_CHECKING:
    # NOTE: TYPE_CHECKING is True when static type checkers are running,
    # allowing for circular imports only for them (mypy, pylance, ruff)
    from ._client import SimcoreSSMAPI


def _map_botocore_client_exception(
    botocore_error: botocore_exc.ClientError, **kwargs
) -> SSMAccessError:
    status_code = int(
        botocore_error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        or botocore_error.response.get("Error", {}).get("Code", -1)
    )
    operation_name = botocore_error.operation_name
    match status_code, operation_name:
        case 400, "SendCommand":
            return SSMSendCommandInstancesNotReadyError()
        case 400, "GetCommandInvocation":
            assert "Error" in botocore_error.response  # nosec
            assert "Message" in botocore_error.response["Error"]  # nosec
            return SSMInvalidCommandError(command_id=kwargs["command_id"])

        case _:
            return SSMAccessError(
                operation_name=operation_name,
                code=status_code,
                error=f"{botocore_error}",
            )


P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")
Self = TypeVar("Self", bound="SimcoreSSMAPI")


def ssm_exception_handler(
    logger: logging.Logger,
) -> Callable[
    [Callable[Concatenate[Self, P], Coroutine[Any, Any, R]]],
    Callable[Concatenate[Self, P], Coroutine[Any, Any, R]],
]:
    """
    Raises:
        SSMAccessError:
    """

    def decorator(
        func: Callable[Concatenate[Self, P], Coroutine[Any, Any, R]],
    ) -> Callable[Concatenate[Self, P], Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(self: Self, *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await func(self, *args, **kwargs)
            except botocore_exc.ClientError as exc:
                raise _map_botocore_client_exception(exc, **kwargs) from exc
            except botocore_exc.WaiterError as exc:
                raise SSMTimeoutError(details=f"{exc}") from exc
            except botocore_exc.EndpointConnectionError as exc:
                raise SSMNotConnectedError from exc
            except botocore_exc.BotoCoreError as exc:
                logger.exception("Unexpected error in SSM client: ")
                raise SSMRuntimeError from exc

        wrapper.__doc__ = f"{func.__doc__}\n\n{ssm_exception_handler.__doc__}"

        return wrapper

    return decorator
