from fastapi import status

from ._base import ApiServerBaseError


class BackEndException(ApiServerBaseError):
    """Base class for all backend exceptions"""

    status_code = status.HTTP_502_BAD_GATEWAY


class ListSolversOrStudiesError(BackEndException):
    msg_template = "Cannot list solvers/studies"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOrStudyNotFoundError(BackEndException):
    msg_template = "Could not get solver/study {name}:{version}"
    status_code = status.HTTP_404_NOT_FOUND


class JobNotFoundError(BackEndException):
    msg_template = "Could not get solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class LogFileNotFound(BackEndException):
    msg_template = "Could not get logfile for solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOutputNotFound(BackEndException):
    msg_template = "Solver {node_uuid} output of project {project_uuid} not found"
    status_code = status.HTTP_404_NOT_FOUND


class ProjectAlreadyStartedException(BackEndException):
    pass
