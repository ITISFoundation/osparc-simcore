class DirectorException(Exception):
    """Basic exception for errors raised with director"""
    def __init__(self, msg=None):
        if msg is None:
            msg = "Unexpected error occured in director subpackage"
        super(DirectorException, self).__init__(msg)

class ServiceNotFoundError(DirectorException):
    """Service was not found in swarm"""
    def __init__(self, service_uuid):
        msg = "Service with uuid {} not found".format(service_uuid)
        super(ServiceNotFoundError, self).__init__(msg)
        self.service_uuid = service_uuid
