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
