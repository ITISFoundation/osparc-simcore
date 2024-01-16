from fastapi import HTTPException, status


class CustomBaseError(Exception):
    pass


class InsufficientCredits(CustomBaseError):
    pass


class MissingWallet(CustomBaseError):
    pass


async def custom_error_handler(exc: CustomBaseError):
    if isinstance(exc, InsufficientCredits):
        return HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=f"{exc}"
        )
    elif isinstance(exc, MissingWallet):
        return HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=f"{exc}"
        )
    else:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encountered unspecified error",
        )
