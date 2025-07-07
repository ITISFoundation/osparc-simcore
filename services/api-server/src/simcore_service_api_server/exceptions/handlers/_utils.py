from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

from common_library.error_codes import ErrorCodeStr
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from ...models.schemas.errors import ErrorGet

ExceptionHandler: TypeAlias = Callable[
    [Request, BaseException], Awaitable[JSONResponse]
]


def create_error_json_response(
    *errors: Any, status_code: int, support_id: ErrorCodeStr | None = None, **kwargs
) -> JSONResponse:
    """
    Converts errors to Error response model defined in the OAS
    """

    error_model = ErrorGet(errors=list(errors), support_id=support_id, **kwargs)
    return JSONResponse(
        content=jsonable_encoder(error_model),
        status_code=status_code,
        **kwargs,
    )
