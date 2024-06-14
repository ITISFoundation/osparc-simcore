from ._base import ApiServerBaseError


class BackEndException(ApiServerBaseError):
    """Base class for all backend exceptions"""

    pass


class SolverNotFoundError(BackEndException):
    msg_template = "Could not get solver/study {name}:{version}"


class ProjectAlreadyStartedException(BackEndException):
    pass
