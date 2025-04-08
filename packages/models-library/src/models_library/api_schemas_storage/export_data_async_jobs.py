# pylint: disable=R6301

from common_library.errors_classes import OsparcErrorMixin

### Exceptions


class StorageRpcBaseError(OsparcErrorMixin, RuntimeError):
    pass


class InvalidFileIdentifierError(StorageRpcBaseError):
    msg_template: str = "Could not find the file {file_id}"


class AccessRightError(StorageRpcBaseError):
    msg_template: str = (
        "User {user_id} does not have access to file {file_id} with location {location_id}"
    )
