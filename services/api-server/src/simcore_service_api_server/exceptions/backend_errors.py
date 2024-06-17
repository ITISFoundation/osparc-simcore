from ._base import ApiServerBaseError


class BackEndException(ApiServerBaseError):
    """Base class for all backend exceptions"""

    pass


class ListSolversOrStudiesError(BackEndException):
    msg_template = "Cannot list solvers/studies"


class SolverOrStudyNotFoundError(BackEndException):
    msg_template = "Could not get solver/study {name}:{version}"


class JobNotFoundError(BackEndException):
    msg_template = "Could not get solver/study job {project_id}"


class LogFileNotFound(BackEndException):
    msg_template = "Could not get logfile for solver/study job {project_id}"


class ProjectAlreadyStartedException(BackEndException):
    pass
