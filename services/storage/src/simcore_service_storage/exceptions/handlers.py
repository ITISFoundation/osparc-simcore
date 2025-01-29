import logging

from asyncpg.exceptions import PostgresError
from aws_library.s3 import S3AccessError, S3KeyNotFoundError
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from servicelib.fastapi.http_error import (
    make_default_http_error_handler,
    make_http_error_handler_for_exception,
)

from ..modules.datcore_adapter.datcore_adapter_exceptions import (
    DatcoreAdapterTimeoutError,
)
from .errors import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
    InvalidFileIdentifierError,
    LinkAlreadyExistsError,
    ProjectAccessRightError,
    ProjectNotFoundError,
)

_logger = logging.getLogger(__name__)


def set_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        HTTPException, make_default_http_error_handler(envelope_error=True)
    )
    app.add_exception_handler(
        HTTPException,
        make_http_error_handler_for_exception(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            HTTPException,
            envelope_error=True,
        ),
    )

    for exc_unprocessable in (ValidationError, RequestValidationError):
        app.add_exception_handler(
            exc_unprocessable,
            make_http_error_handler_for_exception(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                exc_unprocessable,
                envelope_error=True,
            ),
        )

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
        PostgresError,
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

    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_http_error_handler_for_exception(
            status.HTTP_501_NOT_IMPLEMENTED, NotImplementedError, envelope_error=True
        ),
    )
    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR, Exception, envelope_error=True
        ),
    )
