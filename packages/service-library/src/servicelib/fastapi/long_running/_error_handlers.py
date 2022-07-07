from fastapi import status
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse

from ._errors import BaseLongRunningError, TaskNotFoundError


async def base_long_running_error_handler(
    _: Request, exception: BaseLongRunningError
) -> JSONResponse:
    error_fields = dict(code=exception.code, message=f"{exception}")
    status_code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exception, TaskNotFoundError)
        else status.HTTP_400_BAD_REQUEST
    )
    return JSONResponse(content=jsonable_encoder(error_fields), status_code=status_code)
