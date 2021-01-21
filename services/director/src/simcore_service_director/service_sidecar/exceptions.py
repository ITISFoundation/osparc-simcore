from ..exceptions import DirectorException


class ServiceSidecarError(DirectorException):
    def __init__(self, reason: str):
        super().__init__(reason)