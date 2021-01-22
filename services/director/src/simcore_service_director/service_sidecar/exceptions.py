# this needs to be removed when the module will be
# stripped from the director-v1
from ..exceptions import DirectorException


class ServiceSidecarError(DirectorException):
    def __init__(self, reason: str):
        super().__init__(reason)


class GenericDockerError(ServiceSidecarError):
    """Generic docker library error"""

    def __init__(self, msg: str, original_exception: Exception):
        super().__init__(msg + ": {original_exception}")
        self.original_exception = original_exception
