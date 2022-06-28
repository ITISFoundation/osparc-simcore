from pydantic.errors import PydanticErrorMixin


class FileMetaDataNotFoundError(PydanticErrorMixin, RuntimeError):
    code = "filemetadata.not_found_error"
    msg_template: str = "The file meta data for {file_id} was not found"


class FileAccessRightError(PydanticErrorMixin, RuntimeError):
    code = "file.access_right_error"
    msg_template: str = "Insufficient access rights to {access_right} {file_id}"


class ProjectAccessRightError(PydanticErrorMixin, RuntimeError):
    code = "file.access_right_error"
    msg_template: str = "Insufficient access rights to {access_right} {project_id}"


class ProjectNotFoundError(PydanticErrorMixin, RuntimeError):
    code = "project.not_found_error"
    msg_template: str = "Project {project_id} was not found"


class LinkAlreadyExistsError(PydanticErrorMixin, RuntimeError):
    code = "link.already_exists_error"
    msg_template: str = "The link {file_id} already exists"


class S3AccessError(PydanticErrorMixin, RuntimeError):
    code = "s3_access.error"
    msg_template: str = "Unexpected error while accessing S3 backend"


class S3BucketInvalidError(PydanticErrorMixin, RuntimeError):
    code = "s3_bucket.invalid_error"
    msg_template: str = "The {bucket} is invalid"


class S3KeyNotFoundError(PydanticErrorMixin, RuntimeError):
    code = "s3_key.not_found_error"
    msg_template: str = "The file {key}  in {bucket} was not found"
