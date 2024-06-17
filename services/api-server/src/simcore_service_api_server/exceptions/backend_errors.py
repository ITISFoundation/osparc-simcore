from ._base import ApiServerBaseError


class BackEndException(ApiServerBaseError):
    """Base class for all backend exceptions"""

    pass


class CannotListSolversOrStudies(BackEndException):
    msg_template = "Cannot list solvers/studies"


class SolverOrStudyNotFoundError(BackEndException):
    msg_template = "Could not get solver/study {name}:{version}"


class ProjectAlreadyStartedException(BackEndException):
    pass
