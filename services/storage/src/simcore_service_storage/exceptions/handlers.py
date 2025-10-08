import logging

from aws_library.s3 import S3AccessError, S3KeyNotFoundError
from fastapi import FastAPI, status
from servicelib.fastapi.http_error import (
    make_http_error_handler_for_exception,
    set_app_default_http_error_handlers,
)
from sqlalchemy.exc import DBAPIError

from ..modules.datcore_adapter.datcore_adapter_exceptions import (
    DatcoreAdapterFileNotFoundError,
    DatcoreAdapterTimeoutError,
)
from .errors import (
    DatCoreCredentialsMissingError,
    FileAccessRightError,
    FileMetaDataNotFoundError,
    InvalidFileIdentifierError,
    LinkAlreadyExistsError,
    ProjectAccessRightError,
    ProjectNotFoundError,
)

_logger = logging.getLogger(__name__)


def set_exception_handlers(app: FastAPI) -> None:
    set_app_default_http_error_handlers(app)

    #
    # add custom exception handlers
    #
    app.add_exception_handler(
        InvalidFileIdentifierError,
        make_http_error_handler_for_exception(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            InvalidFileIdentifierError,
            envelope_error=True,
        ),
    )
    for exc_not_found in (
        FileMetaDataNotFoundError,
        S3KeyNotFoundError,
        ProjectNotFoundError,
        DatcoreAdapterFileNotFoundError,
    ):
        app.add_exception_handler(
            exc_not_found,
            make_http_error_handler_for_exception(
                status.HTTP_404_NOT_FOUND, exc_not_found, envelope_error=True
            ),
        )
    for exc_access in (
        FileAccessRightError,
        ProjectAccessRightError,
    ):
        app.add_exception_handler(
            exc_access,
            make_http_error_handler_for_exception(
                status.HTTP_403_FORBIDDEN, exc_access, envelope_error=True
            ),
        )
    app.add_exception_handler(
        LinkAlreadyExistsError,
        make_http_error_handler_for_exception(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            LinkAlreadyExistsError,
            envelope_error=True,
        ),
    )
    for exc_3rd_party in (
        DBAPIError,
        S3AccessError,
    ):
        app.add_exception_handler(
            exc_3rd_party,
            make_http_error_handler_for_exception(
                status.HTTP_503_SERVICE_UNAVAILABLE, exc_3rd_party, envelope_error=True
            ),
        )

    app.add_exception_handler(
        DatcoreAdapterTimeoutError,
        make_http_error_handler_for_exception(
            status.HTTP_504_GATEWAY_TIMEOUT,
            DatcoreAdapterTimeoutError,
            envelope_error=True,
        ),
    )
    app.add_exception_handler(
        DatCoreCredentialsMissingError,
        make_http_error_handler_for_exception(
            status.HTTP_401_UNAUTHORIZED,
            DatCoreCredentialsMissingError,
            envelope_error=True,
        ),
    )
