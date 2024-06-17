from fastapi import status

from ._base import ApiServerBaseError


class BackEndException(ApiServerBaseError):
    """Base class for all backend exceptions"""

    status_code = status.HTTP_502_BAD_GATEWAY


class ListSolversOrStudiesError(BackEndException):
    msg_template = "Cannot list solvers/studies"
    status_code = status.HTTP_404_NOT_FOUND


class ListJobsError(BackEndException):
    msg_template = "Cannot list jobs"
    status_code = status.HTTP_404_NOT_FOUND


class PaymentRequiredError(BackEndException):
    msg_template = "Payment required"
    status_code = status.HTTP_402_PAYMENT_REQUIRED


class ProfileNotFoundError(BackEndException):
    msg_template = "Profile not found"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOrStudyNotFoundError(BackEndException):
    msg_template = "Could not get solver/study {name}:{version}"
    status_code = status.HTTP_404_NOT_FOUND


class JobNotFoundError(BackEndException):
    msg_template = "Could not get solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class LogFileNotFoundError(BackEndException):
    msg_template = "Could not get logfile for solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOutputNotFoundError(BackEndException):
    msg_template = "Solver output of project {project_uuid} not found"
    status_code = status.HTTP_404_NOT_FOUND


class ClusterNotFoundError(BackEndException):
    msg_template = "Cluster not found"
    status_code = status.HTTP_406_NOT_ACCEPTABLE


class ConfigurationError(BackEndException):
    msg_template = "Configuration error"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ProductPriceNotFoundError(BackEndException):
    msg_template = "Product price not found"
    status_code = status.HTTP_404_NOT_FOUND


class WalletNotFoundError(BackEndException):
    msg_template = "Wallet not found"
    status_code = status.HTTP_404_NOT_FOUND


class ForbiddenWalletError(BackEndException):
    msg_template = "User does not have access to wallet"
    status_code = status.HTTP_403_FORBIDDEN


class ProjectPortsNotFoundError(BackEndException):
    msg_template = "The ports for the job/study {project_id} could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class ProjectMetadataNotFoundError(BackEndException):
    msg_template = "The metadata for the job/study {project_id} could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class PricingUnitNotFoundError(BackEndException):
    msg_template = "The pricing unit could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class PricingPlanNotFoundError(BackEndException):
    msg_template = "The pricing plan could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class ProjectAlreadyStartedException(BackEndException):
    pass
