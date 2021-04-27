from simcore_service_director_v2.utils.exceptions import DirectorException


class ServiceSidecarError(DirectorException):
    pass


class GenericDockerError(ServiceSidecarError):
    """Generic docker library error"""

    def __init__(self, msg: str, original_exception: Exception):
        super().__init__(msg + ": {original_exception}")
        self.original_exception = original_exception
