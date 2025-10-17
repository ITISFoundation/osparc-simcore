from typing import Any

from aiohttp import web
from common_library.json_serialization import json_dumps
from models_library.rest_error import ErrorGet

from ..status_codes_utils import (
    get_code_display_name,
    is_error,
)
from .rest_responses import safe_status_message


def create_error_context_from_request(request: web.Request) -> dict[str, Any]:
    return {
        "request": request,
        "request.remote": f"{request.remote}",
        "request.method": f"{request.method}",
        "request.path": f"{request.path}",
    }


def create_error_response(error: ErrorGet, status_code: int) -> web.Response:
    assert is_error(status_code), f"{status_code=} must be an error [{error=}]"  # nosec

    return web.json_response(
        data={"error": error.model_dump(exclude_unset=True, mode="json")},
        dumps=json_dumps,
        reason=safe_status_message(get_code_display_name(status_code)),
        status=status_code,
    )
