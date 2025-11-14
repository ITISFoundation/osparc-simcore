"""Extends `aiohttp.web_exceptions` classes to match `status` codes
and adds helper functions.
"""

import inspect
from typing import Any, TypeVar

from aiohttp import web_exceptions
from aiohttp.web_exceptions import (
    HTTPClientError,
    HTTPError,
    HTTPException,
    HTTPServerError,
)

from . import status

assert issubclass(HTTPError, HTTPException)  # nsoec

# NOTE: these are the status codes that DO NOT have an aiohttp.HTTPException associated
STATUS_CODES_WITHOUT_AIOHTTP_EXCEPTION_CLASS = (
    status.HTTP_100_CONTINUE,
    status.HTTP_101_SWITCHING_PROTOCOLS,
    status.HTTP_102_PROCESSING,
    status.HTTP_103_EARLY_HINTS,
    status.HTTP_207_MULTI_STATUS,
    status.HTTP_208_ALREADY_REPORTED,
    status.HTTP_226_IM_USED,
    status.HTTP_306_RESERVED,
    status.HTTP_418_IM_A_TEAPOT,
    status.HTTP_425_TOO_EARLY,
)


class HTTPLockedError(HTTPClientError):
    # pylint: disable=too-many-ancestors
    status_code = status.HTTP_423_LOCKED


class HTTPLoopDetectedError(HTTPServerError):
    # pylint: disable=too-many-ancestors
    status_code = status.HTTP_508_LOOP_DETECTED


E = TypeVar("E", bound="HTTPException")


def get_all_aiohttp_http_exceptions(
    base_http_exception_cls: type[E],
) -> dict[int, type[E]]:
    # Inverse map from code to HTTPException classes

    def _pred(obj) -> bool:
        return (
            inspect.isclass(obj)
            and issubclass(obj, base_http_exception_cls)
            and getattr(obj, "status_code", 0) > 0
        )

    found: list[tuple[str, Any]] = inspect.getmembers(web_exceptions, _pred)
    assert found  # nosec

    status_to_http_exception_map = {cls.status_code: cls for _, cls in found}
    assert len(status_to_http_exception_map) == len(found), "No duplicates"  # nosec

    for cls in (
        HTTPLockedError,
        HTTPLoopDetectedError,
    ):
        status_to_http_exception_map[cls.status_code] = cls

    return status_to_http_exception_map


_STATUS_CODE_TO_HTTP_ERRORS: dict[int, type[HTTPError]] = (
    get_all_aiohttp_http_exceptions(HTTPError)
)


def get_http_error_class_or_none(status_code: int) -> type[HTTPError] | None:
    """Returns aiohttp error class corresponding to a 4XX or 5XX status code

    NOTE: any non-error code (i.e. 2XX, 3XX and 4XX) will return None
    """
    return _STATUS_CODE_TO_HTTP_ERRORS.get(status_code)
