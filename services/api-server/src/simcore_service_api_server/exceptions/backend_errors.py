import parse  # type: ignore[import-untyped]
from fastapi import status

from ._base import ApiServerBaseError


class BaseBackEndError(ApiServerBaseError):
    """status_code: the default return status which will be returned to the client calling the
    api-server (in case this exception is raised)"""

    status_code = status.HTTP_502_BAD_GATEWAY

    @classmethod
    def named_fields(cls) -> set[str]:
        return set(
            parse.compile(cls.msg_template).named_fields  # pylint: disable=no-member
        )


class BackendTimeoutError(BaseBackEndError):
    msg_template = "Backend request timed out"
    status_code = status.HTTP_504_GATEWAY_TIMEOUT


class InvalidInputError(BaseBackEndError):
    msg_template = "Invalid input"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


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


class ProgramOrSolverOrStudyNotFoundError(BaseBackEndError):
    msg_template = "Could not get program/solver/study {name}:{version}"
    status_code = status.HTTP_404_NOT_FOUND


class ServiceForbiddenAccessError(BaseBackEndError):
    msg_template = "Forbidden access to program/solver/study {name}:{version}"
    status_code = status.HTTP_403_FORBIDDEN


class JobForbiddenAccessError(BaseBackEndError):
    msg_template = "Forbidden access to job {project_id}"
    status_code = status.HTTP_403_FORBIDDEN


class JobNotFoundError(BaseBackEndError):
    msg_template = "Could not get solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class LogFileNotFoundError(BaseBackEndError):
    msg_template = "Could not get logfile for solver/study job {project_id}"
    status_code = status.HTTP_404_NOT_FOUND


class SolverOutputNotFoundError(BaseBackEndError):
    msg_template = "Solver output of project {project_id} not found"
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


class InsufficientNumberOfSeatsError(BaseBackEndError):
    msg_template = "Not enough available seats for license item {licensed_item_id}"
    status_code = status.HTTP_409_CONFLICT


class CanNotCheckoutServiceIsNotRunningError(BaseBackEndError):
    msg_template = "Can not checkout license item {licensed_item_id} as dynamic service is not running. Current service id: {service_run_id}"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class LicensedItemCheckoutNotFoundError(BaseBackEndError):
    msg_template = "Licensed item checkout {licensed_item_checkout_id} not found."
    status_code = status.HTTP_404_NOT_FOUND
