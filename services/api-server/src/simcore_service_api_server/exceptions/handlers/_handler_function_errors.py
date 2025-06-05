from fastapi import Request
from models_library.functions_errors import FunctionBaseError

from ._utils import create_error_json_response


async def function_error_handler(request: Request, exc: Exception):
    assert request  # nosec
    assert isinstance(exc, FunctionBaseError)

    return create_error_json_response(f"{exc}", status_code=exc.status_code)
