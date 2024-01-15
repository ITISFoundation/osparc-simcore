from fastapi import HTTPException, status


class CustomBaseError(Exception):
    pass


class InsufficientCredits(CustomBaseError):
    pass


async def custom_error_handler(exc: CustomBaseError):
    if isinstance(exc, InsufficientCredits):
        return HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=f"{exc}"
        )
