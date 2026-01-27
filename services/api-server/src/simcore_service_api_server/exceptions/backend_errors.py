import parse  # type: ignore[import-untyped]
from common_library.user_messages import user_message
from fastapi import status

from ._base import ApiServerBaseError


class BaseBackEndError(ApiServerBaseError):
    """status_code: the default return status which will be returned to the client calling the
    api-server (in case this exception is raised)"""

    msg_template = user_message("An error occurred when contacting the backend service.", _version=1)
    status_code = status.HTTP_502_BAD_GATEWAY

    @classmethod
    def named_fields(cls) -> set[str]:
        return set(
            parse.compile(cls.msg_template).named_fields  # pylint: disable=no-member
        )


class BackendTimeoutError(BaseBackEndError):
    msg_template = user_message("The backend request timed out.", _version=1)
    status_code = status.HTTP_504_GATEWAY_TIMEOUT


class InvalidInputError(BaseBackEndError):
    msg_template = user_message("The provided input is not valid.", _version=1)
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ListSolversOrStudiesError(BaseBackEndError):
    msg_template = user_message("Unable to retrieve the list of solvers and projects.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class ListJobsError(BaseBackEndError):
    msg_template = user_message("Unable to retrieve the list of jobs.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class PaymentRequiredError(BaseBackEndError):
    msg_template = user_message("Payment is required to proceed.", _version=1)
    status_code = status.HTTP_402_PAYMENT_REQUIRED


class ProfileNotFoundError(BaseBackEndError):
    msg_template = user_message("The requested profile could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class ProgramOrSolverOrStudyNotFoundError(BaseBackEndError):
    msg_template = user_message(
        "The program, solver, or project '{name}' version {version} could not be found.",
        _version=1,
    )
    status_code = status.HTTP_404_NOT_FOUND


class ServiceForbiddenAccessError(BaseBackEndError):
    msg_template = user_message(
        "You do not have permission to access the program, solver, or project '{name}' version {version}.",
        _version=1,
    )
    status_code = status.HTTP_403_FORBIDDEN


class JobForbiddenAccessError(BaseBackEndError):
    msg_template = user_message("You do not have permission to access job {project_id}.", _version=1)
    status_code = status.HTTP_403_FORBIDDEN


class JobNotFoundError(BaseBackEndError):
    msg_template = user_message("The solver or project job {project_id} could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class LogFileNotFoundError(BaseBackEndError):
    msg_template = user_message(
        "The log file for the solver or project job {project_id} could not be found.",
        _version=1,
    )
    status_code = status.HTTP_404_NOT_FOUND


class SolverOutputNotFoundError(BaseBackEndError):
    msg_template = user_message("The output for project {project_id} could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class ClusterNotFoundError(BaseBackEndError):
    msg_template = user_message("The requested cluster could not be found.", _version=1)
    status_code = status.HTTP_406_NOT_ACCEPTABLE


class ConfigurationError(BaseBackEndError):
    msg_template = user_message("A configuration error occurred.", _version=1)
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ProductPriceNotFoundError(BaseBackEndError):
    msg_template = user_message("The product price could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class WalletNotFoundError(BaseBackEndError):
    msg_template = user_message("The requested wallet could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class ForbiddenWalletError(BaseBackEndError):
    msg_template = user_message("You do not have permission to access this wallet.", _version=1)
    status_code = status.HTTP_403_FORBIDDEN


class ProjectPortsNotFoundError(BaseBackEndError):
    msg_template = user_message("The ports for job or project {project_id} could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class ProjectMetadataNotFoundError(BaseBackEndError):
    msg_template = user_message("The metadata for job or project {project_id} could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class PricingUnitNotFoundError(BaseBackEndError):
    msg_template = user_message("The pricing unit could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class PricingPlanNotFoundError(BaseBackEndError):
    msg_template = user_message("The pricing plan could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class ProjectAlreadyStartedError(BaseBackEndError):
    msg_template = user_message("The project has already been started.", _version=1)
    status_code = status.HTTP_200_OK


class InsufficientNumberOfSeatsError(BaseBackEndError):
    msg_template = user_message("Not enough available seats for license item {licensed_item_id}.", _version=1)
    status_code = status.HTTP_409_CONFLICT


class CanNotCheckoutServiceIsNotRunningError(BaseBackEndError):
    msg_template = user_message(
        "Unable to check out license item {licensed_item_id} because the dynamic service is not running. Current service ID: {service_run_id}.",
        _version=1,
    )
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class LicensedItemCheckoutNotFoundError(BaseBackEndError):
    msg_template = user_message(
        "The license item checkout {licensed_item_checkout_id} could not be found.",
        _version=1,
    )
    status_code = status.HTTP_404_NOT_FOUND


class JobAssetsMissingError(BaseBackEndError):
    msg_template = user_message("The assets for job {job_id} are missing.", _version=1)
    status_code = status.HTTP_409_CONFLICT


class CeleryTaskNotFoundError(BaseBackEndError):
    msg_template = user_message("Task {task_uuid} could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class SolverJobOutputRequestButNotSucceededError(BaseBackEndError):
    msg_template = user_message(
        "Cannot retrieve output for solver job '{job_id}' because it has not completed successfully. Current state: {state}.",
        _version=1,
    )
    status_code = status.HTTP_409_CONFLICT


class SolverJobNotStoppedYetError(BaseBackEndError):
    msg_template = user_message(
        "Solver job '{job_id}' has not stopped yet. Current status: {state}.",
        _version=1,
    )
    status_code = status.HTTP_409_CONFLICT


class StudyJobOutputRequestButNotSucceededError(BaseBackEndError):
    msg_template = user_message(
        "Cannot retrieve output for project job '{job_id}' because it has not completed successfully. Current state: {state}.",
        _version=1,
    )
    status_code = status.HTTP_409_CONFLICT
