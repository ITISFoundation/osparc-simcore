class BackEndException(Exception):
    """Base class for all backend exceptions"""

    pass


class ProjectAlreadyStartedException(BackEndException):
    pass
