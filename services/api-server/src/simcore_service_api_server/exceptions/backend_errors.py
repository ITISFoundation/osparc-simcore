from fastapi import status

from ._base import ApiServerBaseError


class BackEndError(ApiServerBaseError):
    """Base class for all backend exceptions"""

    status_code = status.HTTP_502_BAD_GATEWAY


class ListSolversOrStudiesError(BackEndError):
    msg_template = "Cannot list solvers/studies"
    status_code = status.HTTP_404_NOT_FOUND


class ListJobsError(BackEndError):
    msg_template = "Cannot list jobs"
    status_code = status.HTTP_404_NOT_FOUND


class PaymentRequiredError(BackEndError):
    msg_template = "Payment required"
    status_code = status.HTTP_402_PAYMENT_REQUIRED


class ProfileNotFoundError(BackEndError):
    msg_template = "Profile not found"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOrStudyNotFoundError(BackEndError):
    msg_template = "Could not get solver/study {name}:{version}"
    status_code = status.HTTP_404_NOT_FOUND


class JobNotFoundError(BackEndError):
    msg_template = "Could not get solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class LogFileNotFoundError(BackEndError):
    msg_template = "Could not get logfile for solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOutputNotFoundError(BackEndError):
    msg_template = "Solver output of project {project_uuid} not found"
    status_code = status.HTTP_404_NOT_FOUND


class ClusterNotFoundError(BackEndError):
    msg_template = "Cluster not found"
    status_code = status.HTTP_406_NOT_ACCEPTABLE


class ConfigurationError(BackEndError):
    msg_template = "Configuration error"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ProductPriceNotFoundError(BackEndError):
    msg_template = "Product price not found"
    status_code = status.HTTP_404_NOT_FOUND


class WalletNotFoundError(BackEndError):
    msg_template = "Wallet not found"
    status_code = status.HTTP_404_NOT_FOUND


class ForbiddenWalletError(BackEndError):
    msg_template = "User does not have access to wallet"
    status_code = status.HTTP_403_FORBIDDEN


class ProjectPortsNotFoundError(BackEndError):
    msg_template = "The ports for the job/study {project_id} could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class ProjectMetadataNotFoundError(BackEndError):
    msg_template = "The metadata for the job/study {project_id} could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class PricingUnitNotFoundError(BackEndError):
    msg_template = "The pricing unit could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class PricingPlanNotFoundError(BackEndError):
    msg_template = "The pricing plan could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class ProjectAlreadyStartedException(BackEndError):
    msg_template = "Project already started"
    status_code = status.HTTP_200_OK
