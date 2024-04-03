import logging

from fastapi import Request, status
from servicelib.error_codes import create_error_code
from starlette.responses import JSONResponse

_logger = logging.getLogger(__name__)


class CustomBaseError(Exception):
    pass


class InsufficientCredits(CustomBaseError):
    pass


class MissingWallet(CustomBaseError):
    pass


class ApplicationSetupError(CustomBaseError):
    pass


async def custom_error_handler(_: Request, exc: CustomBaseError):
    if isinstance(exc, InsufficientCredits):
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, content=f"{exc}"
        )
    if isinstance(exc, MissingWallet):
        return JSONResponse(
            status_code=status.HTTP_424_FAILED_DEPENDENCY, content=f"{exc}"
        )
    error_code = create_error_code(exc)
    _logger.error("Unexpected error", extra={"error_cose": error_code})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=f"Unexpected server error [OEC: {error_code}]",
    )
