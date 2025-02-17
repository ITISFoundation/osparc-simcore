import logging

from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import CatalogForbiddenError

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...folders.errors import FolderAccessForbiddenError, FolderNotFoundError
from ...resource_usage.errors import DefaultPricingPlanNotFoundError
from ...users.exceptions import UserDefaultWalletNotFoundError
from ...wallets.errors import WalletAccessForbiddenError, WalletNotEnoughCreditsError
from ...workspaces.errors import WorkspaceAccessForbiddenError, WorkspaceNotFoundError
from ..exceptions import (
    ClustersKeeperNotAvailableError,
    DefaultPricingUnitNotFoundError,
    NodeNotFoundError,
    ParentNodeNotFoundError,
    ProjectDeleteError,
    ProjectGroupNotFoundError,
    ProjectInDebtCanNotChangeWalletError,
    ProjectInvalidRightsError,
    ProjectInvalidUsageError,
    ProjectNodeRequiredInputsNotSetError,
    ProjectNotFoundError,
    ProjectOwnerNotFoundInTheProjectAccessRightsError,
    ProjectStartsTooManyDynamicNodesError,
    WrongTagIdsInQueryError,
)

_logger = logging.getLogger(__name__)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    #
    # NOTE: keep keys alphabetically sorted
    #
    FolderAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Access to folder forbidden",
    ),
    FolderNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Folder not found: {reason}",
    ),
    NodeNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Node '{node_uuid}' not found in project '{project_uuid}'",
    ),
    ParentNodeNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Parent node '{node_uuid}' not found",
    ),
    ProjectDeleteError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Failed to complete deletion of '{project_uuid}': {reason}",
    ),
    ProjectGroupNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Project group not found: {reason}",
    ),
    ProjectInvalidRightsError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Do not have sufficient access rights on project {project_uuid} for this action",
    ),
    ProjectInvalidUsageError: HttpErrorInfo(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Invalid usage for project",
    ),
    ProjectNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Project {project_uuid} not found",
    ),
    ProjectOwnerNotFoundInTheProjectAccessRightsError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "Project owner identifier was not found in the project's access-rights field",
    ),
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Access to workspace forbidden: {reason}",
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Workspace not found: {reason}",
    ),
    WrongTagIdsInQueryError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "Wrong tag IDs in query",
    ),
    UserDefaultWalletNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "User default wallet not found",
    ),
    DefaultPricingPlanNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Default pricing plan not found",
    ),
    DefaultPricingUnitNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Default pricing unit not found",
    ),
    WalletNotEnoughCreditsError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Wallet does not have enough credits. {reason}",
    ),
    ProjectInDebtCanNotChangeWalletError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Unable to change the credit account linked to the project. The project is embargoed because the last transaction of {debt_amount} resulted in the credit account going negative.",
    ),
    ProjectStartsTooManyDynamicNodesError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "The maximal amount of concurrently running dynamic services was reached. Please manually stop a service and retry.",
    ),
    ClustersKeeperNotAvailableError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Clusters-keeper service is not available",
    ),
    ProjectNodeRequiredInputsNotSetError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Project node is required but input is not set",
    ),
    CatalogForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Catalog forbidden: Insufficient access rights for {name}",
    ),
    WalletAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Payment required, but the user lacks access to the project's linked wallet: Wallet access forbidden. {reason}",
    ),
}
handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
