import inspect
from typing import Any

from aiohttp import web_exceptions
from aiohttp.web_exceptions import HTTPClientError, HTTPError, HTTPException

from . import status


class HTTPLockedError(HTTPClientError):
    # pylint: disable=too-many-ancestors
    status_code = status.HTTP_423_LOCKED


# Inverse map from code to HTTPException classes
def collect_aiohttp_http_exceptions(
    exception_cls: type[HTTPException] = HTTPException,
) -> dict[int, type[HTTPException]]:
    def _pred(obj) -> bool:
        return (
            inspect.isclass(obj)
            and issubclass(obj, exception_cls)
            and getattr(obj, "status_code", 0) > 0
        )

    # TODO: add these here as well
    found: list[tuple[str, Any]] = inspect.getmembers(web_exceptions, _pred)
    assert found  # nosec

    http_statuses = {cls.status_code: cls for _, cls in found}
    assert len(http_statuses) == len(found), "No duplicates"  # nosec

    return http_statuses


_STATUS_CODE_TO_HTTP_ERRORS: dict[
    int, type[HTTPError]
] = collect_aiohttp_http_exceptions(HTTPError)


def get_http_error_class_or_none(status_code: int) -> type[HTTPError] | None:
    """Returns aiohttp error class corresponding to a 4XX or 5XX status code

    NOTE: any non-error code (i.e. 2XX, 3XX and 4XX) will return None
    """
    return _STATUS_CODE_TO_HTTP_ERRORS.get(status_code)
