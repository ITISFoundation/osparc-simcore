import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from servicelib.logging_errors import create_troubleshootting_log_kwargs

from ..services.invitations import InvalidInvitationCodeError

_logger = logging.getLogger(__name__)

INVALID_INVITATION_URL_MSG = "Invalid invitation link"


def handle_invalid_invitation_code_error(request: Request, exception: Exception):
    assert isinstance(exception, InvalidInvitationCodeError)  # nosec
    user_msg = INVALID_INVITATION_URL_MSG

    _logger.warning(
        **create_troubleshootting_log_kwargs(
            user_msg,
            error=exception,
            error_context={
                "request.method": f"{request.method}",
                "request.url": f"{request.url}",
                "request.body": getattr(request, "_json", None),
            },
            tip="An invitation link could not be extracted",
        )
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": user_msg},
    )


def setup(app: FastAPI):
    app.add_exception_handler(
        InvalidInvitationCodeError, handle_invalid_invitation_code_error
    )
