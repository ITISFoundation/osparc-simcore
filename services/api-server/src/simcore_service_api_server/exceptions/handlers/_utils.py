from typing import Any

from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from ...models.schemas.errors import ErrorGet


def create_error_json_response(
    *errors: Any, status_code: int, **kwargs
) -> JSONResponse:
    """
    Converts errors to Error response model defined in the OAS
    """

    # NOTE: do not forget to add in the decorator `responses={ ???: {"model": ErrorGet} }`
    # SEE https://fastapi.tiangolo.com/advanced/additional-responses/#additional-response-with-model
    error_model = ErrorGet(errors=list(errors))
    return JSONResponse(
        content=jsonable_encoder(error_model),
        status_code=status_code,
        **kwargs,
    )
