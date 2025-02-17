import logging

from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)

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
    ProjectInDebtCanNotOpenError,
    ProjectInvalidRightsError,
    ProjectInvalidUsageError,
    ProjectNodeRequiredInputsNotSetError,
    ProjectNotFoundError,
    ProjectOwnerNotFoundInTheProjectAccessRightsError,
    ProjectStartsTooManyDynamicNodesError,
    ProjectTooManyProjectOpenedError,
    ProjectWalletPendingTransactionError,
    WrongTagIdsInQueryError,
)

_logger = logging.getLogger(__name__)


_FOLDER_ERRORS: ExceptionToHttpErrorMap = {
    FolderAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Access to folder forbidden",
    ),
    FolderNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Folder not found: {reason}",
    ),
}


_NODE_ERRORS: ExceptionToHttpErrorMap = {
    NodeNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Node '{node_uuid}' not found in project '{project_uuid}'",
    ),
    ParentNodeNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Parent node '{node_uuid}' not found",
    ),
    ProjectNodeRequiredInputsNotSetError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Project node is required but input is not set",
    ),
}


_PROJECT_ERRORS: ExceptionToHttpErrorMap = {
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
    ProjectTooManyProjectOpenedError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "You cannot open more than {max_num_projects} study/ies at once. Please close another study and retry.",
    ),
    ProjectStartsTooManyDynamicNodesError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "The maximal amount of concurrently running dynamic services was reached. Please manually stop a service and retry.",
    ),
    ProjectWalletPendingTransactionError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Project has currently pending transactions. It is forbidden to change wallet.",
    ),
    ProjectInDebtCanNotChangeWalletError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Unable to change the credit account linked to the project. The project is embargoed because the last transaction of {debt_amount} resulted in the credit account going negative.",
    ),
    ProjectInDebtCanNotOpenError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Unable to open the project. The project is embargoed because the last transaction of {debt_amount} resulted in the credit account going negative.",
    ),
    WrongTagIdsInQueryError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "Wrong tag IDs in query",
    ),
}


_WORKSPACE_ERRORS: ExceptionToHttpErrorMap = {
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Access to workspace forbidden: {reason}",
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Workspace not found: {reason}",
    ),
}


_WALLET_ERRORS: ExceptionToHttpErrorMap = {
    UserDefaultWalletNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Wallet not found: {reason}",
    ),
    WalletAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Payment required, but the user lacks access to the project's linked wallet: Wallet access forbidden. {reason}",
    ),
    WalletNotEnoughCreditsError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Wallet does not have enough credits. {reason}",
    ),
}


_PRICING_ERRORS: ExceptionToHttpErrorMap = {
    DefaultPricingPlanNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Default pricing plan not found",
    ),
    DefaultPricingUnitNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Default pricing unit not found",
    ),
}


_OTHER_ERRORS: ExceptionToHttpErrorMap = {
    ClustersKeeperNotAvailableError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Clusters-keeper service is not available",
    ),
    CatalogForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Catalog forbidden: Insufficient access rights for {name}",
    ),
    CatalogItemNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND, "{name} was not found"
    ),
}

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {}
_TO_HTTP_ERROR_MAP.update(_FOLDER_ERRORS)
_TO_HTTP_ERROR_MAP.update(_NODE_ERRORS)
_TO_HTTP_ERROR_MAP.update(_PROJECT_ERRORS)
_TO_HTTP_ERROR_MAP.update(_WORKSPACE_ERRORS)
_TO_HTTP_ERROR_MAP.update(_WALLET_ERRORS)
_TO_HTTP_ERROR_MAP.update(_PRICING_ERRORS)
_TO_HTTP_ERROR_MAP.update(_OTHER_ERRORS)

handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
