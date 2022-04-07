from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse

from .errors import BaseDynamicSidecarError


async def http_error_handler(_: Request, exc: BaseDynamicSidecarError) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder({"errors": [exc.message]}), status_code=exc.status
    )
