from fastapi import FastAPI, HTTPException, status

from ..errors import RutNotFoundError
from ._http_error import (
    http404_error_handler,
    http_error_handler,
    make_http_error_handler_for_exception,
)


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RutNotFoundError, http404_error_handler)

    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR, Exception
        ),
    )
