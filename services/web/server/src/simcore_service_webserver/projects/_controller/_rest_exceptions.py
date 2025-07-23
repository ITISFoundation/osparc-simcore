import itertools
import logging
from collections import Counter

from common_library.user_messages import user_message
from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
    CatalogNotAvailableError,
)

from ...catalog._controller_rest_exceptions import catalog_exceptions_handlers_map
from ...conversations.errors import (
    ConversationErrorNotFoundError,
    ConversationMessageErrorNotFoundError,
)
from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...exception_handling._base import ExceptionHandlersMap
from ...folders.errors import FolderAccessForbiddenError, FolderNotFoundError
from ...resource_usage.errors import DefaultPricingPlanNotFoundError
from ...users.exceptions import UserDefaultWalletNotFoundError
from ...wallets.errors import WalletAccessForbiddenError, WalletNotEnoughCreditsError
from ...workspaces.errors import WorkspaceAccessForbiddenError, WorkspaceNotFoundError
from ..exceptions import (
    ClustersKeeperNotAvailableError,
    DefaultPricingUnitNotFoundError,
    InsufficientRoleForProjectTemplateTypeUpdateError,
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
    ProjectTooManyUserSessionsError,
    ProjectTypeAndTemplateIncompatibilityError,
    ProjectWalletPendingTransactionError,
    WrongTagIdsInQueryError,
)

_logger = logging.getLogger(__name__)


_FOLDER_ERRORS: ExceptionToHttpErrorMap = {
    FolderAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("Access to this folder is forbidden.", _version=1),
    ),
    FolderNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The requested folder could not be found: {reason}", _version=1),
    ),
}


_NODE_ERRORS: ExceptionToHttpErrorMap = {
    NodeNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "Node '{node_uuid}' was not found in project '{project_uuid}'.", _version=1
        ),
    ),
    ParentNodeNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Parent node '{node_uuid}' was not found.", _version=1),
    ),
    ProjectNodeRequiredInputsNotSetError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "Required input values for this project node have not been set.", _version=1
        ),
    ),
}


_PROJECT_ERRORS: ExceptionToHttpErrorMap = {
    ProjectDeleteError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "Unable to complete deletion of project '{project_uuid}': {reason}",
            _version=1,
        ),
    ),
    ProjectGroupNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The requested project group could not be found: {reason}", _version=1
        ),
    ),
    ProjectInvalidRightsError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "You do not have sufficient access rights to perform this action on project {project_uuid}.",
            _version=1,
        ),
    ),
    InsufficientRoleForProjectTemplateTypeUpdateError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "You do not have sufficient permissions to update the project template type.",
            _version=1,
        ),
    ),
    ProjectInvalidUsageError: HttpErrorInfo(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        user_message("The project cannot be used in this way.", _version=1),
    ),
    ProjectNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Project {project_uuid} could not be found.", _version=1),
    ),
    ProjectOwnerNotFoundInTheProjectAccessRightsError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "The project owner could not be found in the project's access rights.",
            _version=1,
        ),
    ),
    ProjectTooManyProjectOpenedError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "You cannot open more than {max_num_projects} project/s at once. Please close another project and retry.",
            _version=2,
        ),
    ),
    ProjectStartsTooManyDynamicNodesError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "The maximum number of concurrently running dynamic services has been reached. Please manually stop a service and retry.",
            _version=1,
        ),
    ),
    ProjectWalletPendingTransactionError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "This project has pending transactions. Changing the wallet is currently not allowed.",
            _version=1,
        ),
    ),
    ProjectTooManyUserSessionsError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "You cannot open more than {max_num_sessions} session(s) for the same project at once. Please close another session and retry.",
            _version=1,
        ),
    ),
    ProjectInDebtCanNotChangeWalletError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        user_message(
            "Unable to change the credit account linked to the project. The project is embargoed because the last transaction of {debt_amount} resulted in the credit account going negative.",
            _version=1,
        ),
    ),
    ProjectInDebtCanNotOpenError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        user_message(
            "Unable to open the project. The project is embargoed because the last transaction of {debt_amount} resulted in the credit account going negative.",
            _version=1,
        ),
    ),
    WrongTagIdsInQueryError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message("Invalid tag IDs were provided in the request.", _version=1),
    ),
    ProjectTypeAndTemplateIncompatibilityError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "The project type and template type combination is not valid: {reason}",
            _version=1,
        ),
    ),
}


_WORKSPACE_ERRORS: ExceptionToHttpErrorMap = {
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("Access to this workspace is forbidden: {reason}", _version=1),
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The requested workspace could not be found: {reason}", _version=1
        ),
    ),
}


_WALLET_ERRORS: ExceptionToHttpErrorMap = {
    UserDefaultWalletNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The requested wallet could not be found: {reason}", _version=1),
    ),
    WalletAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "Payment is required, but you do not have access to the project's linked wallet: {reason}",
            _version=1,
        ),
    ),
    WalletNotEnoughCreditsError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        user_message(
            "The wallet does not have enough credits to complete this operation: {reason}",
            _version=1,
        ),
    ),
}


_PRICING_ERRORS: ExceptionToHttpErrorMap = {
    DefaultPricingPlanNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The default pricing plan could not be found.", _version=1),
    ),
    DefaultPricingUnitNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The default pricing unit could not be found.", _version=1),
    ),
}


_CONVERSATION_ERRORS: ExceptionToHttpErrorMap = {
    ConversationErrorNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The requested conversation could not be found.", _version=1),
    ),
    ConversationMessageErrorNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The requested conversation message could not be found.", _version=1
        ),
    ),
}


_OTHER_ERRORS: ExceptionToHttpErrorMap = {
    CatalogNotAvailableError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message("The catalog service is currently unavailable.", _version=1),
    ),
    ClustersKeeperNotAvailableError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message(
            "The clusters-keeper service is currently unavailable.", _version=1
        ),
    ),
    CatalogForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "Access denied: You do not have sufficient permissions for {name}.",
            _version=1,
        ),
    ),
    CatalogItemNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The requested item '{name}' was not found.", _version=1),
    ),
}


_ERRORS = [
    _CONVERSATION_ERRORS,
    _FOLDER_ERRORS,
    _NODE_ERRORS,
    _OTHER_ERRORS,
    _PRICING_ERRORS,
    _PROJECT_ERRORS,
    _WALLET_ERRORS,
    _WORKSPACE_ERRORS,
]


def _assert_duplicate():
    duplicates = {
        exc.__name__: count
        for exc, count in Counter(itertools.chain(*[d.keys() for d in _ERRORS])).items()
        if count > 1
    }
    if duplicates:
        msg = f"Found duplicated exceptions: {duplicates}"
        raise AssertionError(msg)
    return True


assert _assert_duplicate()  # nosec

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    k: v for dikt in _ERRORS for k, v in dikt.items()
}


_handlers: ExceptionHandlersMap = {
    **catalog_exceptions_handlers_map,
    **to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP),
}

handle_plugin_requests_exceptions = exception_handling_decorator(_handlers)
