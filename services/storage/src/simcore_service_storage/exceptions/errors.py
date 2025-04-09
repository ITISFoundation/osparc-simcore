from common_library.errors_classes import OsparcErrorMixin


class StorageRuntimeError(OsparcErrorMixin, RuntimeError): ...


class ConfigurationError(StorageRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


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


class AccessLayerError(StorageRuntimeError):
    msg_template: str = "Database access layer error"


class InvalidFileIdentifierError(AccessLayerError):
    msg_template: str = "Error in {identifier}: {details}"


class DatCoreCredentialsMissingError(StorageRuntimeError):
    msg_template: str = "DatCore credentials are incomplete. TIP: Check your settings"


class SelectionNotAllowedError(StorageRuntimeError):
    msg_template: str = "Selection='{selection}' must share the same parent folder"
