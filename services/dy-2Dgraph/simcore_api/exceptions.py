class SimcoreException(Exception):
    """Basic exception for errors raised in simcore_api"""
    def __init__(self, msg=None):
        if msg is None:
            msg = "An error occured in simcore"
        super(SimcoreException, self).__init__(msg)

class UnboundPortError(SimcoreException):
    """Accessed port is not configured"""
    def __init__(self, port_index, msg=None):
        msg = "No port bound at index %s" % (port_index)
        super(UnboundPortError, self).__init__(msg)
        self.port_index = port_index