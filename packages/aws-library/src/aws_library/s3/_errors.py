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
