# Errors raised by node_ports module as NodeportsException
#
#
#  NOTE: Error message SHALL explain the reason for the error and it is prefered in one line, i.e. avoid '\n' in message
#
#


class NodeportsException(Exception):
    """Basic exception for errors raised in nodeports"""

    def __init__(self, msg: str | None = None):
        super().__init__(msg or "An error occured in simcore")


class ReadOnlyError(NodeportsException):
    """Trying to modify read-only object"""

    def __init__(self, obj):
        super().__init__(f"Trying to modify read-only object {obj}")
        self.obj = obj


class UnboundPortError(NodeportsException, IndexError):
    """Accessed port is not configured"""

    def __init__(self, port_index, msg: str | None = None):
        super().__init__(f"No port bound at index {port_index}")
        self.port_index = port_index


class InvalidKeyError(NodeportsException):
    """Accessed key does not exist"""

    def __init__(self, item_key: str, msg: str | None = None):
        super().__init__(f"No port bound with key {item_key}")
        self.item_key = item_key


class InvalidItemTypeError(NodeportsException):
    """Item type incorrect"""

    def __init__(self, item_type: str, item_value: str, msg: str | None = None):
        super().__init__(
            msg
            or f"Invalid item type, value [{item_value}] does not qualify as type [{item_type}]"
        )
        self.item_type = item_type
        self.item_value = item_value


class InvalidProtocolError(NodeportsException):
    """Invalid protocol used"""

    def __init__(self, dct, msg: str | None = None):
        super().__init__(f"Invalid protocol used: {dct} [{msg}]")
        self.dct = dct


class StorageInvalidCall(NodeportsException):
    """Storage returned an error 400<=status<500"""


class StorageServerIssue(NodeportsException):
    """Storage returned an error status>=500"""


class S3TransferError(NodeportsException):
    """S3 transfer error"""

    def __init__(self, msg: str | None = None):
        super().__init__(msg or "Error while transferring to/from S3 storage")


class S3InvalidPathError(NodeportsException):
    """S3 transfer error"""

    def __init__(self, s3_object_name):
        super().__init__(f"No object in S3 storage at {s3_object_name}")
        self.object_name = s3_object_name


class S3InvalidStore(NodeportsException):
    """S3 transfer error"""

    def __init__(self, s3_store):
        super().__init__(f"Invalid store used: {s3_store}")
        self.store = s3_store


class InvalidDownloadLinkError(NodeportsException):
    """Download link is invalid"""

    def __init__(self, link):
        super().__init__(f"Invalid link [{link}]")
        self.link = link


class TransferError(NodeportsException):
    """Download/Upload transfer error"""

    def __init__(self, link):
        super().__init__(f"Error while transferring to/from [{link}]")
        self.link = link


class StorageConnectionError(NodeportsException):
    """S3 transfer error"""

    def __init__(self, s3_store, additional_msg=None):
        super().__init__(f"Connection to store {s3_store} failed: {additional_msg}")
        self.store = s3_store


class PortNotFound(NodeportsException):
    """Accessed key does not exist"""


class NodeNotFound(NodeportsException):
    """The given node_uuid was not found"""

    def __init__(self, node_uuid):
        self.node_uuid = node_uuid
        super().__init__(f"the node id {node_uuid} was not found")


class ProjectNotFoundError(NodeportsException):
    """The given node_uuid was not found"""

    def __init__(self, project_id):
        self.project_id = project_id
        super().__init__(f"the {project_id=} was not found")


class SymlinkToSymlinkIsNotUploadableException(NodeportsException):
    """Not possible to upload a symlink to a symlink"""

    def __init__(self, symlink, symlink_target_path):
        message = (
            f"'{symlink}' is pointing to '{symlink_target_path}' "
            "which is itself a symlink. This is not supported!"
        )
        super().__init__(message)
        self.symlink = symlink
        self.symlink_target_path = symlink_target_path


class AbsoluteSymlinkIsNotUploadableException(NodeportsException):
    """absolute symlink is not uploadable"""

    def __init__(self, symlink, symlink_target_path):
        message = (
            f"Absolute symlinks are not supported: "
            f"{symlink} points to {symlink_target_path} "
            "Try with relative symlinks!"
        )
        super().__init__(message)
        self.symlink = symlink
        self.symlink_target_path = symlink_target_path
