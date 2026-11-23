"""Public HTTP rendering of the projects errors shared with other domains.

``project_product_mismatch_exceptions_handlers_map`` is reused by other domains
(e.g. director-v2) so ``ProjectProductMismatchError`` renders the same response
on every endpoint that raises it. Consumers import this module as a namespace;
the ``_PROJECT_PRODUCT_MISMATCH_ERRORS`` map is private to the projects domain.
"""

from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ..exception_handling import (
    ExceptionHandlersMap,
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    to_exceptions_handlers_map,
)
from .exceptions import ProjectProductMismatchError

_PROJECT_PRODUCT_MISMATCH_ERRORS: ExceptionToHttpErrorMap = {
    ProjectProductMismatchError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "The project belongs to a different product than the one requested.",
            _version=1,
        ),
    ),
}

project_product_mismatch_exceptions_handlers_map: ExceptionHandlersMap = to_exceptions_handlers_map(
    _PROJECT_PRODUCT_MISMATCH_ERRORS
)

__all__: tuple[str, ...] = ("project_product_mismatch_exceptions_handlers_map",)  # nopycln: file
