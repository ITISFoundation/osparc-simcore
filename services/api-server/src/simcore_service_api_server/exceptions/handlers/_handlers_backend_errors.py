import logging

from common_library.error_codes import create_error_code
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error
from starlette.requests import Request
from starlette.responses import JSONResponse

from ...exceptions.backend_errors import BaseBackEndError
from ._utils import create_error_json_response

_logger = logging.getLogger(__name__)


async def backend_error_handler(
    request: Request, exc: BaseBackEndError
) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, BaseBackEndError)
    user_error_msg = f"{exc}"
    support_id = None
    if is_5xx_server_error(exc.status_code):
        support_id = create_error_code(exc)
        _logger.exception(
            **create_troubleshootting_log_kwargs(
                user_error_msg,
                error=exc,
                error_code=support_id,
                tip="Unexpected error",
            )
        )
    return create_error_json_response(
        user_error_msg, status_code=exc.status_code, support_id=support_id
    )
