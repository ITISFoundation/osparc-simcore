from servicelib.aiohttp import status
from simcore_service_webserver.api_keys.errors import (
    ApiKeyNotFoundError,
    ApiKeysValueError,
)
from simcore_service_webserver.exceptions_handlers import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    create_exception_handlers_decorator,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    ApiKeyNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "API key was not found",
    ),
}


handle_plugin_requests_exceptions = create_exception_handlers_decorator(
    exceptions_catch=(ApiKeysValueError,),
    exc_to_status_map=_TO_HTTP_ERROR_MAP,
)
