import logging

from common_library.error_codes import create_error_code
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error
from starlette.requests import Request
from starlette.responses import JSONResponse

from ...exceptions.usage_limit_errors import ChatboxUsageBaseError
from ._utils import create_error_json_response

_logger = logging.getLogger(__name__)


async def usage_limit_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, ChatboxUsageBaseError)  # nosec

    support_id = None
    if is_5xx_server_error(exc.status_code):
        # server-side rejections (e.g. the usage ledger failing closed on a Redis outage)
        # must leave operational traces; a user simply exceeding quota does not
        support_id = create_error_code(exc)
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                f"{exc}",
                error=exc,
                error_code=support_id,
                tip="Check the api-server connection to the Chatbox usage Redis database.",
            )
        )

    headers = {}
    if (retry_after := exc.retry_after_seconds) is not None:
        headers["Retry-After"] = f"{retry_after}"

    return create_error_json_response(f"{exc}", status_code=exc.status_code, support_id=support_id, headers=headers)
