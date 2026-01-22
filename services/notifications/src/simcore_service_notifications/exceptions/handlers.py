import logging

from fastapi import FastAPI, status
from servicelib.fastapi.http_error import (
    make_http_error_handler_for_exception,
    set_app_default_http_error_handlers,
)

from .errors import (
    TemplateNotFoundError,
    VariablesModelNotFoundError,
)

_logger = logging.getLogger(__name__)


def set_exception_handlers(app: FastAPI) -> None:
    set_app_default_http_error_handlers(app)

    #
    # custom exception handlers
    #
    for exc_not_found in (
        TemplateNotFoundError,
        VariablesModelNotFoundError,
    ):
        app.add_exception_handler(
            exc_not_found,
            make_http_error_handler_for_exception(status.HTTP_404_NOT_FOUND, exc_not_found, envelope_error=True),
        )
