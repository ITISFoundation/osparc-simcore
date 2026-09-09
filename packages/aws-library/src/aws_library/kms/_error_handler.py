import functools
import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar

from botocore import exceptions as botocore_exc

from ._errors import (
    KMSAccessError,
    KMSInvalidCiphertextError,
    KMSKeyNotFoundError,
    KMSNotConnectedError,
    KMSRuntimeError,
)

if TYPE_CHECKING:
    # NOTE: TYPE_CHECKING is True when static type checkers are running,
    # allowing for circular imports only for them (mypy, pylance, ruff)
    from ._client import SimcoreKMSAPI


def _map_botocore_client_exception(botocore_error: botocore_exc.ClientError, **kwargs) -> KMSAccessError:
    error_code = botocore_error.response.get("Error", {}).get("Code")
    status_code = int(botocore_error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") or -1)
    operation_name = botocore_error.operation_name
    match error_code:
        case "NotFoundException":
            return KMSKeyNotFoundError(key_id=kwargs.get("key_id"))
        case "InvalidCiphertextException":
            return KMSInvalidCiphertextError()
        case _:
            return KMSAccessError(
                operation_name=operation_name,
                code=status_code,
                error=f"{botocore_error}",
            )


P = ParamSpec("P")
R = TypeVar("R")
Self = TypeVar("Self", bound="SimcoreKMSAPI")


def kms_exception_handler(
    logger: logging.Logger,
) -> Callable[
    [Callable[Concatenate[Self, P], Coroutine[Any, Any, R]]],
    Callable[Concatenate[Self, P], Coroutine[Any, Any, R]],
]:
    """
    Raises:
        KMSAccessError:
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
            except botocore_exc.EndpointConnectionError as exc:
                raise KMSNotConnectedError from exc
            except botocore_exc.BotoCoreError as exc:
                logger.exception("Unexpected error in KMS client: ")
                raise KMSRuntimeError from exc

        wrapper.__doc__ = f"{func.__doc__}\n\n{kms_exception_handler.__doc__}"

        return wrapper

    return decorator
