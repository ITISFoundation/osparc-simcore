from fastapi import Request, status
from starlette.responses import JSONResponse

from ...models.custom_errors import (
    CustomBaseError,
    InsufficientCreditsError,
    MissingWalletError,
)


async def custom_error_handler(_: Request, exc: CustomBaseError):
    if isinstance(exc, InsufficientCreditsError):
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, content=f"{exc}"
        )
    if isinstance(exc, MissingWalletError):
        return JSONResponse(
            status_code=status.HTTP_424_FAILED_DEPENDENCY, content=f"{exc}"
        )
