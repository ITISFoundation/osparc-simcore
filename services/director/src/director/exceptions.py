"""Defines the different exceptions that may arise in the director"""
class DirectorException(Exception):
    """Basic exception"""
    def __init__(self, msg=None):
        if msg is None:
            msg = "Unexpected error was triggered"
        super(DirectorException, self).__init__(msg)

class GenericDockerError(DirectorException):
    """Generic docker library error"""
    def __init__(self, msg, original_exception):
        msg = msg + (": %s" % original_exception)
        super(GenericDockerError, self).__init__(msg)

class ServiceNotFoundError(DirectorException):
    """Service not found"""
    def __init__(self, service_name, service_tag):
        msg = "The service %s:%s was not found" % (service_name, service_tag)
        super(ServiceNotFoundError, self).__init__(msg)
        self.service_name = service_name

class ServiceUUIDInUseError(DirectorException):
    """Service UUID is already in use"""
    def __init__(self, service_uuid):
        msg = "The service uuid %s is already in use" % (service_uuid)
        super(ServiceUUIDInUseError, self).__init__(msg)
        self.service_uuid = service_uuid

class RegistryConnectionError(DirectorException):
    """Error while connecting to the docker regitry"""
    def __init__(self, msg=None):
        if msg is None:
            msg = "Impossible to connect to docker registry"
        super(RegistryConnectionError, self).__init__(msg)

class ServiceStartTimeoutError(DirectorException):
    """The service was created but never run (time-out)"""
    def __init__(self, service_name, service_uuid):
        msg = "Service %s:%s failed to start " %(service_name, service_uuid)
        super(ServiceStartTimeoutError, self).__init__(msg)
        self.service_name = service_name
        self.service_uuid = service_uuid