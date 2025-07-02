import logging

from common_library.error_codes import create_error_code
from fastapi import status
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from starlette.requests import Request
from starlette.responses import JSONResponse

from ...exceptions.backend_errors import BaseBackEndError
from ._utils import create_error_json_response

_logger = logging.getLogger(__name__)


async def backend_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, BaseBackEndError)
    user_error_msg = f"{exc}"
    if not exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        oec = create_error_code(exc)
        user_error_msg += f" [{oec}]"
        _logger.exception(
            **create_troubleshootting_log_kwargs(
                user_error_msg,
                error=exc,
                error_code=oec,
                tip="Unexpected error",
            )
        )
    return create_error_json_response(user_error_msg, status_code=exc.status_code)
