import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from servicelib.logging_errors import create_troubleshotting_log_kwargs

from ..services.invitations import InvalidInvitationCodeError

_logger = logging.getLogger(__name__)

INVALID_INVITATION_URL_MSG = "Invalid invitation link"


def handle_invalid_invitation_code_error(request: Request, exception: Exception):
    assert isinstance(exception, InvalidInvitationCodeError)  # nosec
    user_msg = INVALID_INVITATION_URL_MSG
    _logger.warning(
        **create_troubleshotting_log_kwargs(
            user_msg,
            error=exception,
            error_context={
                "request": f"{request}",
                "request.method": f"{request.method}",
                "request.path": f"{request.url.path}",
            },
            tip="Some invitation link is invalid. Note that the encryption key for generation/check must be the same!",
        )
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": INVALID_INVITATION_URL_MSG},
    )


def setup(app: FastAPI):
    app.add_exception_handler(
        InvalidInvitationCodeError, handle_invalid_invitation_code_error
    )
