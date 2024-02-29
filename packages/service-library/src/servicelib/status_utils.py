""" Usage

    - on aiohttp services
        from servicelib.aiohttp import status
        from servicelib.status_utils import is_success

        assert is_success(status.HTTP_200_OK)


    - on fastapi services

        from fastapi import status
        from servicelib.status_utils import is_success

        assert is_success(status.HTTP_200_OK)

    NOTE: https://github.com/encode/httpx/blob/master/httpx/_status_codes.py
"""

import types
from collections.abc import Callable
from http import HTTPStatus


def get_display_phrase(status_code: int | HTTPStatus) -> str:
    try:
        status_code = HTTPStatus(status_code)
        return f"{status_code}:{status_code.phrase}"
    except ValueError:
        return f"{status_code}"


def is_informational(status_code: int) -> bool:
    """
    Returns `True` for 1xx status codes, `False` otherwise.
    """
    return 100 <= status_code <= 199


def is_success(status_code: int) -> bool:
    """
    Returns `True` for 2xx status codes, `False` otherwise.
    """
    return 200 <= status_code <= 299


def is_redirect(status_code: int) -> bool:
    """
    Returns `True` for 3xx status codes, `False` otherwise.
    """
    return 300 <= status_code <= 399


def is_client_error(status_code: int) -> bool:
    """
    Returns `True` for 4xx status codes, `False` otherwise.
    """
    return 400 <= status_code <= 499


def is_server_error(status_code: int) -> bool:
    """
    Returns `True` for 5xx status codes, `False` otherwise.
    """
    return 500 <= status_code <= 599


def is_error(status_code: int) -> bool:
    """
    Returns `True` for 4xx or 5xx status codes, `False` otherwise.
    """
    return 400 <= status_code <= 599


def get_http_status_codes(
    status: types.ModuleType, predicate: Callable[[int], bool] | None = None
) -> list[int]:
    # In the spirit of https://docs.python.org/3/library/inspect.html#inspect.getmembers
    iter_all = (
        getattr(status, code) for code in status.__all__ if code.startswith("HTTP_")
    )
    if predicate is None:
        return list(iter_all)
    return [code for code in iter_all if predicate(code)]
