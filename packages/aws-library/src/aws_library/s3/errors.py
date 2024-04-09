import functools
import logging

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


def s3_exception_handler(log: logging.Logger):
    """converts typical aiobotocore/boto exceptions to storage exceptions
    NOTE: this is a work in progress as more exceptions might arise in different
    use-cases
    """

    def decorator(func):  # noqa: C901
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except self.client.exceptions.NoSuchBucket as exc:
                raise S3BucketInvalidError(
                    bucket=exc.response.get("Error", {}).get("BucketName", "undefined")
                ) from exc
            except botocore_exc.ClientError as exc:
                status_code = int(exc.response.get("Error", {}).get("Code", -1))
                operation_name = exc.operation_name

                match status_code, operation_name:
                    case 404, "HeadObject":
                        raise S3KeyNotFoundError(bucket=args[0], key=args[1]) from exc
                    case (404, "HeadBucket") | (403, "HeadBucket"):
                        raise S3BucketInvalidError(bucket=args[0]) from exc
                    case _:
                        raise S3AccessError from exc
            except botocore_exc.EndpointConnectionError as exc:
                raise S3AccessError from exc

            except botocore_exc.BotoCoreError as exc:
                log.exception("Unexpected error in s3 client: ")
                raise S3AccessError from exc

        return wrapper

    return decorator
