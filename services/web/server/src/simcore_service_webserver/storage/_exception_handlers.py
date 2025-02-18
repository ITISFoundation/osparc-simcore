from models_library.api_schemas_storage.data_export_async_jobs import (
    AccessRightError,
    DataExportError,
    InvalidFileIdentifierError,
)
from servicelib.aiohttp import status
from simcore_service_webserver.exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    InvalidFileIdentifierError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Could not find file.",
    ),
    AccessRightError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Accessright error.",
    ),
    DataExportError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Could not export data.",
    ),
}


handle_data_export_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
