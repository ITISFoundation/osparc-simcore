import functools
import logging

from botocore import exceptions as botocore_exc
from pydantic import ByteSize

from .exceptions import S3AccessError, S3BucketInvalidError, S3KeyNotFoundError


def compute_num_file_chunks(file_size: ByteSize) -> tuple[int, ByteSize]:
    return 1, file_size


def s3_exception_handler(log: logging.Logger):
    """converts typical aiobotocore/boto exceptions to storage exceptions
    NOTE: this is a work in progress as more exceptions might arise in different
    use-cases
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                response = await func(self, *args, **kwargs)
            except self.client.exceptions.NoSuchBucket as exc:
                raise S3BucketInvalidError(
                    bucket=exc.response.get("Error", {}).get("BucketName", "undefined")
                ) from exc
            except botocore_exc.ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "404":
                    if exc.operation_name == "HeadObject":
                        raise S3KeyNotFoundError(bucket=args[0], key=args[1]) from exc
                    if exc.operation_name == "HeadBucket":
                        raise S3BucketInvalidError(bucket=args[0]) from exc
                if exc.response.get("Error", {}).get("Code") == "403":
                    if exc.operation_name == "HeadBucket":
                        raise S3BucketInvalidError(bucket=args[0]) from exc
                raise S3AccessError from exc

            except Exception:
                log.exception("Unexpected error in s3 client: ")
                raise

            return response

        return wrapper

    return decorator
