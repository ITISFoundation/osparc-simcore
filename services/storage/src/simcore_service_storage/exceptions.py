from aws_library.s3.errors import (
    S3AccessError,
    S3BucketInvalidError,
    S3KeyNotFoundError,
)
from pydantic.errors import PydanticErrorMixin


class StorageRuntimeError(PydanticErrorMixin, RuntimeError):
    ...


class DatabaseAccessError(StorageRuntimeError):
    code = "database.access_error"
    msg_template: str = "Unexpected error while accessing database backend"


class FileMetaDataNotFoundError(DatabaseAccessError):
    code = "filemetadata.not_found_error"
    msg_template: str = "The file meta data for {file_id} was not found"


class FileAccessRightError(DatabaseAccessError):
    code = "file.access_right_error"
    msg_template: str = "Insufficient access rights to {access_right} data {file_id}"


class ProjectAccessRightError(DatabaseAccessError):
    code = "file.access_right_error"
    msg_template: str = (
        "Insufficient access rights to {access_right} project {project_id}"
    )


class ProjectNotFoundError(DatabaseAccessError):
    code = "project.not_found_error"
    msg_template: str = "Project {project_id} was not found"


class LinkAlreadyExistsError(DatabaseAccessError):
    code = "link.already_exists_error"
    msg_template: str = "The link {file_id} already exists"


assert S3AccessError  # nosec
assert S3BucketInvalidError  # nosec
assert S3KeyNotFoundError  # nosec


__all__: tuple[str, ...] = (
    "S3AccessError",
    "S3BucketInvalidError",
    "S3KeyNotFoundError",
)
