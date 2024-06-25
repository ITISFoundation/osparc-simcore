import functools
import inspect
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Concatenate, ParamSpec, TypeVar

from botocore import exceptions as botocore_exc
from pydantic.errors import PydanticErrorMixin


class S3RuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "S3 client unexpected error"


class S3NotConnectedError(S3RuntimeError):
    msg_template: str = "Cannot connect with s3 server"


class S3AccessError(S3RuntimeError):
    code = "s3_access.error"
    msg_template: str = "Unexpected error while accessing S3 backend"


class S3BucketInvalidError(S3AccessError):
    code = "s3_bucket.invalid_error"
    msg_template: str = "The bucket '{bucket}' is invalid"


class S3KeyNotFoundError(S3AccessError):
    code = "s3_key.not_found_error"
    msg_template: str = "The file {key}  in {bucket} was not found"


class S3UploadNotFoundError(S3AccessError):
    code = "s3_upload.not_found_error"
    msg_template: str = "The upload for {key}  in {bucket} was not found"


class S3DestinationNotEmptyError(S3AccessError):
    code = "s3_destination.not_empty_error"
    msg_template: str = "The destination {dst_prefix} is not empty"


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


def _map_s3_exception() -> S3AccessError:
    return S3AccessError()


P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")
WrappedFunc = Callable[Concatenate["SimcoreS3API", P], Awaitable[R]]  # type: ignore[name-defined]  # noqa: F821
WrappedAsyncGenFunc = Callable[Concatenate["SimcoreS3API", P], AsyncGenerator[T, None]]  # type: ignore[name-defined]  # noqa: F821


def s3_exception_handler(
    logger: logging.Logger,
) -> Callable[[WrappedFunc | WrappedAsyncGenFunc], WrappedFunc | WrappedAsyncGenFunc]:
    """
    Raises:
        S3BucketInvalidError:
        S3KeyNotFoundError:
        S3BucketInvalidError:
        S3UploadNotFoundError:
        S3AccessError:
    """

    def decorator(  # noqa: C901
        func: WrappedFunc | WrappedAsyncGenFunc,
    ) -> WrappedFunc | WrappedAsyncGenFunc:
        @functools.wraps(func)
        async def awaitable_wrapper(self: "SimcoreS3API", *args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore # noqa: F821
            try:
                result = func(self, *args, **kwargs)
                assert inspect.isawaitable(result)  # nosec
                return await result
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

        @functools.wraps(func)
        async def async_generator_wrapper(self: "SimcoreS3API", *args: P.args, **kwargs: P.kwargs) -> AsyncGenerator[T, None]:  # type: ignore # noqa: F821
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

        wrapped_func = (
            async_generator_wrapper
            if inspect.isasyncgenfunction(func)
            else awaitable_wrapper
        )
        wrapped_func.__doc__ = f"{func.__doc__}\n\n{s3_exception_handler.__doc__}"
        return wrapped_func

    return decorator
