import logging

from asyncpg import PostgresError
from aws_library.s3 import S3AccessError, S3KeyNotFoundError
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from servicelib.fastapi.http_error import (
    http422_error_handler,
    http_error_handler,
    make_http_error_handler_for_exception,
)

from ...exceptions.errors import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
    LinkAlreadyExistsError,
    ProjectAccessRightError,
    ProjectNotFoundError,
)
from ...modules.datcore_adapter.datcore_adapter_exceptions import (
    DatcoreAdapterTimeoutError,
)
from ...modules.db.db_access_layer import InvalidFileIdentifierError

_logger = logging.getLogger(__name__)


def set_exception_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    # director-v2 core.errors mappend into HTTP errors
    app.add_exception_handler(
        InvalidFileIdentifierError,
        make_http_error_handler_for_exception(
            status.HTTP_422_UNPROCESSABLE_ENTITY, InvalidFileIdentifierError
        ),
    )
    for exc_class in (
        FileMetaDataNotFoundError,
        S3KeyNotFoundError,
        ProjectNotFoundError,
    ):
        app.add_exception_handler(
            exc_class,
            make_http_error_handler_for_exception(status.HTTP_404_NOT_FOUND, exc_class),
        )
    for exc_class in (FileAccessRightError, ProjectAccessRightError):
        app.add_exception_handler(
            exc_class,
            make_http_error_handler_for_exception(status.HTTP_403_FORBIDDEN, exc_class),
        )
    app.add_exception_handler(
        LinkAlreadyExistsError,
        make_http_error_handler_for_exception(
            status.HTTP_422_UNPROCESSABLE_ENTITY, LinkAlreadyExistsError
        ),
    )
    for exc_class in (PostgresError, S3AccessError):
        app.add_exception_handler(
            exc_class,
            make_http_error_handler_for_exception(
                status.HTTP_503_SERVICE_UNAVAILABLE, exc_class
            ),
        )

    app.add_exception_handler(
        DatcoreAdapterTimeoutError,
        make_http_error_handler_for_exception(
            status.HTTP_504_GATEWAY_TIMEOUT, DatcoreAdapterTimeoutError
        ),
    )

    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_http_error_handler_for_exception(
            status.HTTP_501_NOT_IMPLEMENTED, NotImplementedError
        ),
    )
    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR, Exception
        ),
    )
