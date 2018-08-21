"""Defines the different exceptions that may arise in the director"""
class DirectorException(Exception):
    """Basic exception"""
    def __init__(self, msg=None):
        if msg is None:
            msg = "Unexpected error was triggered"
        super(DirectorException, self).__init__(msg)

class ServiceNotFoundError(DirectorException):
    """Service not found"""
    def __init__(self, service_name):
        msg = "The service %s was not found" % (service_name)
        super(ServiceNotFoundError, self).__init__(msg)
        self.service_name = service_name

class ServiceUUIDInUseError(DirectorException):
    """Service UUID is already in use"""
    def __init__(self, service_uuid):
        msg = "The service uuid %s is already in use" % (service_uuid)
        super(ServiceUUIDInUseError, self).__init__(msg)
        self.service_uuid = service_uuid
