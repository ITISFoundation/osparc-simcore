from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..models.schemas.errors import ErrorGet


def create_error_json_response(*errors, status_code: int) -> JSONResponse:
    # NOTE: do not forget to add in the decorator `responses={ ???: {"model": ErrorGet} }`
    # SEE https://fastapi.tiangolo.com/advanced/additional-responses/#additional-response-with-model
    error_model = ErrorGet(errors=list(errors))
    return JSONResponse(content=jsonable_encoder(error_model), status_code=status_code)


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return create_error_json_response(exc.detail, status_code=exc.status_code)
