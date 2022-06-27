from pydantic.errors import PydanticErrorMixin


class FileMetaDataNotFoundError(PydanticErrorMixin, RuntimeError):
    code = "filemetadata.not_found_error"
    msg_template: str = "The file meta data for {file_id} was not found"


class S3BucketInvalidError(PydanticErrorMixin, RuntimeError):
    code = "s3_bucket.invalid_error"
    msg_template: str = "The {bucket} is invalid"


class S3KeyNotFoundError(PydanticErrorMixin, RuntimeError):
    code = "s3_key.not_found_error"
    msg_template: str = "The file {key}  in {bucket} was not found"
