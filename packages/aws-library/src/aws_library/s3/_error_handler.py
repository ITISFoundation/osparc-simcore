import functools
import inspect
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar

from botocore import exceptions as botocore_exc

from ._errors import (
    S3AccessError,
    S3BucketInvalidError,
    S3KeyNotFoundError,
    S3UploadNotFoundError,
)


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


def s3_exception_handler(
    logger: logging.Logger,
) -> Callable[  # type: ignore[name-defined]
    [Callable[Concatenate["SimcoreS3API", P], Coroutine[Any, Any, R]]],
    Callable[Concatenate["SimcoreS3API", P], Coroutine[Any, Any, R]],
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
        func: Callable[Concatenate["SimcoreS3API", P], Coroutine[Any, Any, R]]  # type: ignore[name-defined]  # noqa: F821
    ) -> Callable[Concatenate["SimcoreS3API", P], Coroutine[Any, Any, R]]:  # type: ignore[name-defined]  # noqa: F821
        @functools.wraps(func)
        async def wrapper(self: "SimcoreS3API", *args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore[name-defined]  # noqa: F821
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
) -> Callable[  # type: ignore[name-defined]
    [Callable[Concatenate["SimcoreS3API", P], AsyncGenerator[T, None]]],  # noqa: F821
    Callable[Concatenate["SimcoreS3API", P], AsyncGenerator[T, None]],  # noqa: F821
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
        func: Callable[Concatenate["SimcoreS3API", P], AsyncGenerator[T, None]]  # type: ignore[name-defined]  # noqa: F821
    ) -> Callable[Concatenate["SimcoreS3API", P], AsyncGenerator[T, None]]:  # type: ignore[name-defined]  # noqa: F821
        @functools.wraps(func)
        async def async_generator_wrapper(
            self: "SimcoreS3API", *args: P.args, **kwargs: P.kwargs  # type: ignore[name-defined]  # noqa: F821
        ) -> AsyncGenerator[T, None]:
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
            f"{func.__doc__}\n\n{s3_exception_handler.__doc__}"
        )
        return async_generator_wrapper

    return decorator
