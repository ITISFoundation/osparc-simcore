from simcore_service_api_server.exceptions.backend_errors import BaseBackEndError
from starlette.requests import Request
from starlette.responses import JSONResponse

from ._utils import create_error_json_response


async def backend_error_handler(
    request: Request, exc: BaseBackEndError
) -> JSONResponse:
    assert request  # nosec
    return create_error_json_response(f"{exc}", status_code=exc.status_code)
