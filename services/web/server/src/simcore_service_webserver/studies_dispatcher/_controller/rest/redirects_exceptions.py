import functools
import logging

from aiohttp import web
from common_library.error_codes import create_error_code
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from common_library.user_messages import user_message
from models_library.function_services_catalog._utils import ServiceNotFound
from servicelib.aiohttp import status
from servicelib.aiohttp.typing_extension import Handler

from ....exception_handling import create_error_context_from_request
from ....utils import compose_support_error_msg
from ....utils_aiohttp import create_redirect_to_page_response
from ..._constants import MSG_UNEXPECTED_DISPATCH_ERROR
from ..._errors import (
    FileToLargeError,
    GuestUserNotAllowedError,
    GuestUsersLimitError,
    IncompatibleServiceError,
    InvalidRedirectionParamsError,
    ProjectWorkbenchMismatchError,
)

_logger = logging.getLogger(__name__)

#
# HELPERS
#


def _create_redirect_response_to_error_page(
    app: web.Application, message: str, status_code: int
) -> web.HTTPFound:
    # NOTE: these are 'error' page params and need to be interpreted by front-end correctly!
    return create_redirect_to_page_response(
        app,
        page="error",
        message=message,
        status_code=status_code,
    )


def _create_error_redirect_with_logging(
    request: web.Request,
    err: Exception,
    *,
    message: str,
    status_code: int,
    tip: str | None = None,
) -> web.HTTPFound:
    """Helper to create error redirect with consistent logging"""
    error_code = create_error_code(err)
    user_error_msg = compose_support_error_msg(msg=message, error_code=error_code)

    _logger.exception(
        **create_troubleshooting_log_kwargs(
            user_error_msg,
            error=err,
            error_code=error_code,
            error_context=create_error_context_from_request(request),
            tip=tip,
        )
    )

    return _create_redirect_response_to_error_page(
        request.app,
        message=user_error_msg,
        status_code=status_code,
    )


def _create_simple_error_redirect(
    request: web.Request,
    public_error: Exception,
    *,
    status_code: int,
) -> web.HTTPFound:
    """Helper to create simple error redirect without logging

    WARNING: note that the `public_error` is exposed as-is in the user-message
    """
    user_error_msg = user_message(
        f"Unable to open your project: {public_error}", _version=1
    )
    return _create_redirect_response_to_error_page(
        request.app,
        message=user_error_msg,
        status_code=status_code,
    )


def handle_errors_with_error_page(handler: Handler):
    @functools.wraps(handler)
    async def _wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (web.HTTPRedirection, web.HTTPSuccessful):
            # NOTE: that response is a redirection that is reraised and not returned
            raise

        except GuestUserNotAllowedError as err:
            raise _create_redirect_response_to_error_page(
                request.app,
                message=user_message(
                    "Access is restricted to registered users.<br/><br/>"
                    "If you don't have an account, please contact support to request one.<br/><br/>",
                    _version=2,
                ),
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from err

        except ProjectWorkbenchMismatchError as err:
            raise _create_error_redirect_with_logging(
                request,
                err,
                message=MSG_UNEXPECTED_DISPATCH_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                tip="project might be corrupted",
            ) from err

        except (
            ServiceNotFound,
            FileToLargeError,
            IncompatibleServiceError,
            GuestUsersLimitError,
        ) as err:
            raise _create_simple_error_redirect(
                request,
                err,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from err

        except (InvalidRedirectionParamsError, web.HTTPUnprocessableEntity) as err:
            # Validation error in query parameters
            raise _create_error_redirect_with_logging(
                request,
                err,
                message=user_message(
                    "The link you provided is invalid because it doesn't contain valid information related to data or a service. "
                    "Please check the link and make sure it is correct.",
                    _version=1,
                ),
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                tip="The link might be corrupted",
            ) from err

        except web.HTTPClientError as err:
            raise _create_error_redirect_with_logging(
                request,
                err,
                message="Fatal error while redirecting request",
                status_code=err.status_code,
                tip="The link might be corrupted",
            ) from err

        except Exception as err:
            raise _create_error_redirect_with_logging(
                request,
                err,
                message=MSG_UNEXPECTED_DISPATCH_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                tip="Unexpected failure while dispatching study",
            ) from err

    return _wrapper
