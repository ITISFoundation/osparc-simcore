from common_library.errors_classes import OsparcErrorMixin


class StorageRuntimeError(OsparcErrorMixin, RuntimeError):
    ...


class DatabaseAccessError(StorageRuntimeError):
    msg_template: str = "Unexpected error while accessing database backend"


class FileMetaDataNotFoundError(DatabaseAccessError):
    msg_template: str = "The file meta data for {file_id} was not found"


class FileAccessRightError(DatabaseAccessError):
    msg_template: str = "Insufficient access rights to {access_right} data {file_id}"


class ProjectAccessRightError(DatabaseAccessError):
    msg_template: str = (
        "Insufficient access rights to {access_right} project {project_id}"
    )


class ProjectNotFoundError(DatabaseAccessError):
    msg_template: str = "Project {project_id} was not found"


class LinkAlreadyExistsError(DatabaseAccessError):
    msg_template: str = "The link {file_id} already exists"
