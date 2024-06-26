from fastapi import status

from ._base import ApiServerBaseError


class BaseBackEndError(ApiServerBaseError):
    """status_code: the default return status which will be returned to the client calling the
    api-server (in case this exception is raised)"""

    status_code = status.HTTP_502_BAD_GATEWAY


class ListSolversOrStudiesError(BaseBackEndError):
    msg_template = "Cannot list solvers/studies"
    status_code = status.HTTP_404_NOT_FOUND


class ListJobsError(BaseBackEndError):
    msg_template = "Cannot list jobs"
    status_code = status.HTTP_404_NOT_FOUND


class PaymentRequiredError(BaseBackEndError):
    msg_template = "Payment required"
    status_code = status.HTTP_402_PAYMENT_REQUIRED


class ProfileNotFoundError(BaseBackEndError):
    msg_template = "Profile not found"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOrStudyNotFoundError(BaseBackEndError):
    msg_template = "Could not get solver/study {name}:{version}"
    status_code = status.HTTP_404_NOT_FOUND


class JobNotFoundError(BaseBackEndError):
    msg_template = "Could not get solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class LogFileNotFoundError(BaseBackEndError):
    msg_template = "Could not get logfile for solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOutputNotFoundError(BaseBackEndError):
    msg_template = "Solver output of project {project_uuid} not found"
    status_code = status.HTTP_404_NOT_FOUND


class ClusterNotFoundError(BaseBackEndError):
    msg_template = "Cluster not found"
    status_code = status.HTTP_406_NOT_ACCEPTABLE


class ConfigurationError(BaseBackEndError):
    msg_template = "Configuration error"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ProductPriceNotFoundError(BaseBackEndError):
    msg_template = "Product price not found"
    status_code = status.HTTP_404_NOT_FOUND


class WalletNotFoundError(BaseBackEndError):
    msg_template = "Wallet not found"
    status_code = status.HTTP_404_NOT_FOUND


class ForbiddenWalletError(BaseBackEndError):
    msg_template = "User does not have access to wallet"
    status_code = status.HTTP_403_FORBIDDEN


class ProjectPortsNotFoundError(BaseBackEndError):
    msg_template = "The ports for the job/study {project_id} could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class ProjectMetadataNotFoundError(BaseBackEndError):
    msg_template = "The metadata for the job/study {project_id} could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class PricingUnitNotFoundError(BaseBackEndError):
    msg_template = "The pricing unit could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class PricingPlanNotFoundError(BaseBackEndError):
    msg_template = "The pricing plan could not be found"
    status_code = status.HTTP_404_NOT_FOUND


class ProjectAlreadyStartedError(BaseBackEndError):
    msg_template = "Project already started"
    status_code = status.HTTP_200_OK
