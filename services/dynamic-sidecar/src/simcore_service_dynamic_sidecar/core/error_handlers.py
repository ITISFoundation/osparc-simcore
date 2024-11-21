from fastapi import status
from fastapi.encoders import jsonable_encoder
from simcore_sdk.node_ports_common.exceptions import NodeNotFound
from starlette.requests import Request
from starlette.responses import JSONResponse

from .errors import BaseDynamicSidecarError


async def http_error_handler(
    _: Request, exception: BaseDynamicSidecarError
) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder({"errors": [exception.message]}),
        status_code=exception.status_code,  # type:ignore[attr-defined]
    )


async def node_not_found_error_handler(
    _: Request, exception: NodeNotFound
) -> JSONResponse:
    error_fields = {
        "code": "dynamic_sidecar.nodeports.node_not_found",
        "message": f"{exception}",
        "node_uuid": f"{exception.node_uuid}",
    }
    return JSONResponse(
        content=jsonable_encoder(error_fields),
        status_code=status.HTTP_404_NOT_FOUND,
    )
