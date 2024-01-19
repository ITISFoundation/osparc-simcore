from urllib.request import Request

from fastapi import status
from starlette.responses import JSONResponse


class CustomBaseError(Exception):
    pass


class InsufficientCredits(CustomBaseError):
    pass


class MissingWallet(CustomBaseError):
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
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content="Encountered unspecified error",
    )
