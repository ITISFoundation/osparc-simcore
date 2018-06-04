"""Defines the different exceptions that may arise in the simcore_api package"""
class SimcoreException(Exception):
    """Basic exception for errors raised in simcore_api"""
    def __init__(self, msg=None):
        if msg is None:
            msg = "An error occured in simcore"
        super(SimcoreException, self).__init__(msg)

class ReadOnlyError(SimcoreException):
    """Trying to modify read-only object"""
    def __init__(self, obj):
        msg = "Trying to modify read-only object %s" % (obj)
        super(ReadOnlyError, self).__init__(msg)
        self.obj = obj

class WrongProtocolVersionError(SimcoreException):
    """Using wrong protocol version"""
    def __init__(self, expected_version, found_version):
        msg = "Expecting version %s, found version %s" % (expected_version, found_version)
        super(WrongProtocolVersionError, self).__init__(msg)
        self.expected_version = expected_version
        self.found_version = found_version

class UnboundPortError(SimcoreException, IndexError):
    """Accessed port is not configured"""
    def __init__(self, port_index, msg=None):
        msg = "No port bound at index %s" % (port_index)
        super(UnboundPortError, self).__init__(msg)
        self.port_index = port_index

class InvalidProtocolError(SimcoreException):
    """Invalid protocol used"""
    def __init__(self, dct):
        msg = "Invalid protocol used in %s" % (dct)
        super(InvalidProtocolError, self).__init__(msg)
        self.dct = dct
