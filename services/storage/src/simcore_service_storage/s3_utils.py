import functools
import logging
from typing import Final

from botocore import exceptions as botocore_exc
from pydantic import ByteSize, parse_obj_as

from .exceptions import S3AccessError, S3BucketInvalidError, S3KeyNotFoundError

# this is artifically defined, if possible we keep a maximum number of requests for parallel
# uploading. If that is not possible then we create as many upload part as the max part size allows
_MULTIPART_UPLOADS_TARGET_MAX_PART_SIZE: Final[list[ByteSize]] = [
    parse_obj_as(ByteSize, x)
    for x in [
        "10Mib",
        "50Mib",
        "100Mib",
        "200Mib",
        "400Mib",
        "600Mib",
        "800Mib",
        "1Gib",
        "2Gib",
        "3Gib",
        "4Gib",
        "5Gib",
    ]
]
_MULTIPART_MAX_NUMBER_OF_PARTS: Final[int] = 10000


def compute_num_file_chunks(file_size: ByteSize) -> tuple[int, ByteSize]:
    for chunk in _MULTIPART_UPLOADS_TARGET_MAX_PART_SIZE:
        num_upload_links = int(file_size / chunk) + (1 if file_size % chunk > 0 else 0)
        if num_upload_links < _MULTIPART_MAX_NUMBER_OF_PARTS:
            return (num_upload_links, chunk)
    raise ValueError(
        f"Could not determine number of upload links for {file_size=}",
    )


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
            except botocore_exc.EndpointConnectionError as exc:
                raise S3AccessError from exc

            except botocore_exc.BotoCoreError as exc:
                log.exception("Unexpected error in s3 client: ")
                raise S3AccessError from exc

            return response

        return wrapper

    return decorator
