from fastapi import Request, status

from ..custom_errors import (
    CustomBaseError,
    InsufficientCreditsError,
    MissingWalletError,
)
from ._utils import create_error_json_response


async def custom_error_handler(request: Request, exc: Exception):
    assert request  # nosec
    assert isinstance(exc, CustomBaseError)

    error_msg = f"{exc}"
    if isinstance(exc, InsufficientCreditsError):
        return create_error_json_response(
            error_msg, status_code=status.HTTP_402_PAYMENT_REQUIRED
        )
    if isinstance(exc, MissingWalletError):
        return create_error_json_response(
            error_msg, status_code=status.HTTP_424_FAILED_DEPENDENCY
        )

    msg = f"Exception handler is not implement for {exc=} [{type(exc)}]"
    raise NotImplementedError(msg)
