"""Defines the different exceptions that may arise in the nodeports package"""


class NodeportsException(Exception):
    """Basic exception for errors raised in nodeports"""

    def __init__(self, msg=None):
        super().__init__(msg or "An error occured in simcore")


class ReadOnlyError(NodeportsException):
    """Trying to modify read-only object"""

    def __init__(self, obj):
        super().__init__(f"Trying to modify read-only object {obj}")
        self.obj = obj


class WrongProtocolVersionError(NodeportsException):
    """Using wrong protocol version"""

    def __init__(self, expected_version, found_version):
        super().__init__(
            f"Expecting version {expected_version}, found version {found_version}"
        )
        self.expected_version = expected_version
        self.found_version = found_version


class UnboundPortError(NodeportsException, IndexError):
    """Accessed port is not configured"""

    def __init__(self, port_index, msg=None):
        super().__init__(f"No port bound at index {port_index}")
        self.port_index = port_index


class InvalidKeyError(NodeportsException):
    """Accessed key does not exist"""

    def __init__(self, item_key, msg=None):
        super().__init__("No port bound with key {item_key}")
        self.item_key = item_key


class InvalidItemTypeError(NodeportsException):
    """Item type incorrect"""

    def __init__(self, item_type, item_value):
        super().__init__(
            "Invalid item type, {item_value} is set as being a {item_type} type"
        )
        self.item_type = item_type
        self.item_value = item_value


class InvalidProtocolError(NodeportsException):
    """Invalid protocol used"""

    def __init__(self, dct, msg=None):
        super().__init__(f"Invalid protocol used: {dct}\n{msg}")
        self.dct = dct


class StorageInvalidCall(NodeportsException):
    """S3 transfer error"""


class StorageServerIssue(NodeportsException):
    """S3 transfer error"""


class S3TransferError(NodeportsException):
    """S3 transfer error"""

    def __init__(self, msg=None):
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
        super().__init__(f"the node id {node_uuid} was not found")
