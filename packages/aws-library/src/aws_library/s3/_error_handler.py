import functools
import inspect
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar

from botocore import exceptions as botocore_exc

from ._errors import (
    S3AccessError,
    S3BucketInvalidError,
    S3KeyNotFoundError,
    S3UploadNotFoundError,
)

if TYPE_CHECKING:
    # NOTE: TYPE_CHECKING is True when static type checkers are running,
    # allowing for circular imports only for them (mypy, pylance, ruff)
    from ._client import SimcoreS3API


def _map_botocore_client_exception(
    botocore_error: botocore_exc.ClientError, **kwargs
) -> S3AccessError:
    status_code = int(
        botocore_error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        or botocore_error.response.get("Error", {}).get("Code", -1)
    )
    operation_name = botocore_error.operation_name
    match status_code, operation_name:
        case 404, "HeadObject":
            return S3KeyNotFoundError(
                bucket=kwargs["bucket"],
                key=kwargs.get("object_key") or kwargs.get("src_object_key"),
            )
        case (404, "HeadBucket") | (403, "HeadBucket"):
            return S3BucketInvalidError(bucket=kwargs["bucket"])
        case (404, "AbortMultipartUpload") | (
            500,
            "CompleteMultipartUpload",
        ):
            return S3UploadNotFoundError(
                bucket=kwargs["bucket"], key=kwargs["object_key"]
            )
        case _:
            return S3AccessError()


P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")
Self = TypeVar("Self", bound="SimcoreS3API")


def s3_exception_handler(
    logger: logging.Logger,
) -> Callable[
    [Callable[Concatenate[Self, P], Coroutine[Any, Any, R]]],
    Callable[Concatenate[Self, P], Coroutine[Any, Any, R]],
]:
    """
    Raises:
        S3BucketInvalidError:
        S3KeyNotFoundError:
        S3BucketInvalidError:
        S3UploadNotFoundError:
        S3AccessError:
    """

    def decorator(
        func: Callable[Concatenate[Self, P], Coroutine[Any, Any, R]],
    ) -> Callable[Concatenate[Self, P], Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(self: Self, *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await func(self, *args, **kwargs)
            except (
                self._client.exceptions.NoSuchBucket  # pylint: disable=protected-access
            ) as exc:
                raise S3BucketInvalidError(
                    bucket=exc.response.get("Error", {}).get("BucketName", "undefined")
                ) from exc
            except botocore_exc.ClientError as exc:
                raise _map_botocore_client_exception(exc, **kwargs) from exc
            except botocore_exc.EndpointConnectionError as exc:
                raise S3AccessError from exc
            except botocore_exc.BotoCoreError as exc:
                logger.exception("Unexpected error in s3 client: ")
                raise S3AccessError from exc

        wrapper.__doc__ = f"{func.__doc__}\n\n{s3_exception_handler.__doc__}"

        return wrapper

    return decorator


def s3_exception_handler_async_gen(
    logger: logging.Logger,
) -> Callable[
    [Callable[Concatenate[Self, P], AsyncGenerator[T]]],
    Callable[Concatenate[Self, P], AsyncGenerator[T]],
]:
    """
    Raises:
        S3BucketInvalidError:
        S3KeyNotFoundError:
        S3BucketInvalidError:
        S3UploadNotFoundError:
        S3AccessError:
    """

    def decorator(
        func: Callable[Concatenate[Self, P], AsyncGenerator[T]],
    ) -> Callable[Concatenate[Self, P], AsyncGenerator[T]]:
        @functools.wraps(func)
        async def async_generator_wrapper(
            self: Self, *args: P.args, **kwargs: P.kwargs
        ) -> AsyncGenerator[T]:
            try:
                assert inspect.isasyncgenfunction(func)  # nosec
                async for item in func(self, *args, **kwargs):
                    yield item
            except (
                self._client.exceptions.NoSuchBucket  # pylint: disable=protected-access
            ) as exc:
                raise S3BucketInvalidError(
                    bucket=exc.response.get("Error", {}).get("BucketName", "undefined")
                ) from exc
            except botocore_exc.ClientError as exc:
                raise _map_botocore_client_exception(exc, **kwargs) from exc
            except botocore_exc.EndpointConnectionError as exc:
                raise S3AccessError from exc
            except botocore_exc.BotoCoreError as exc:
                logger.exception("Unexpected error in s3 client: ")
                raise S3AccessError from exc

        async_generator_wrapper.__doc__ = (
            f"{func.__doc__}\n\n{s3_exception_handler_async_gen.__doc__}"
        )
        return async_generator_wrapper

    return decorator
