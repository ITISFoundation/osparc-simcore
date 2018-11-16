"""Defines the different exceptions that may arise in the nodeports package"""
class NodeportsException(Exception):
    """Basic exception for errors raised in nodeports"""
    def __init__(self, msg=None):
        if msg is None:
            msg = "An error occured in simcore"
        super(NodeportsException, self).__init__(msg)

class ReadOnlyError(NodeportsException):
    """Trying to modify read-only object"""
    def __init__(self, obj):
        msg = "Trying to modify read-only object %s" % (obj)
        super(ReadOnlyError, self).__init__(msg)
        self.obj = obj

class WrongProtocolVersionError(NodeportsException):
    """Using wrong protocol version"""
    def __init__(self, expected_version, found_version):
        msg = "Expecting version %s, found version %s" % (expected_version, found_version)
        super(WrongProtocolVersionError, self).__init__(msg)
        self.expected_version = expected_version
        self.found_version = found_version

class UnboundPortError(NodeportsException, IndexError):
    """Accessed port is not configured"""
    def __init__(self, port_index, msg=None):
        msg = "No port bound at index %s" % (port_index)
        super(UnboundPortError, self).__init__(msg)
        self.port_index = port_index

class InvalidKeyError(NodeportsException):
    """Accessed key does not exist"""
    def __init__(self, item_key, msg=None):
        msg = "No port bound with key %s" % (item_key)
        super(InvalidKeyError, self).__init__(msg)
        self.item_key = item_key

class InvalidItemTypeError(NodeportsException):
    """Item type incorrect"""
    def __init__(self, item_type, item_value):
        msg = "Invalid item type, %s is set as being a %s type" % (item_value, item_type)
        super(InvalidItemTypeError, self).__init__(msg)
        self.item_type = item_type
        self.item_value = item_value

class InvalidProtocolError(NodeportsException):
    """Invalid protocol used"""
    def __init__(self, dct, msg=None):
        msg = "Invalid protocol used: %s\n%s" % (dct, msg)
        super(InvalidProtocolError, self).__init__(msg)
        self.dct = dct

class StorageInvalidCall(NodeportsException):
    """S3 transfer error"""
    def __init__(self, msg):
        super(StorageInvalidCall, self).__init__(msg)

class StorageServerIssue(NodeportsException):
    """S3 transfer error"""
    def __init__(self, msg):
        super(StorageServerIssue, self).__init__(msg)
        

class S3TransferError(NodeportsException):
    """S3 transfer error"""
    def __init__(self, msg=None):
        if not msg:
            msg = "Error while transferring to/from S3 storage"
        super(S3TransferError, self).__init__(msg)

class S3InvalidPathError(NodeportsException):
    """S3 transfer error"""
    def __init__(self, s3_object_name):
        msg = "No object in S3 storage at {object}".format(object=s3_object_name)
        super(S3InvalidPathError, self).__init__(msg)
        self.object_name = s3_object_name

class S3InvalidStore(NodeportsException):
    """S3 transfer error"""
    def __init__(self, s3_store):
        msg = "Invalid store used: {store}".format(store=s3_store)
        super(S3InvalidStore, self).__init__(msg)
        self.store = s3_store

class StorageConnectionError(NodeportsException):
    """S3 transfer error"""
    def __init__(self, s3_store, additional_msg=None):
        msg = "Connection to store {store} failed: {yamsg}".format(store=s3_store, yamsg=additional_msg)
        super(StorageConnectionError, self).__init__(msg)
        self.store = s3_store

class PortNotFound(NodeportsException):
    """Accessed key does not exist"""
    def __init__(self, msg):
        super(PortNotFound, self).__init__(msg)
