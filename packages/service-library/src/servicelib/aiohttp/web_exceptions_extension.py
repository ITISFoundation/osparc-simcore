from aiohttp.web_exceptions import HTTPClientError

from . import status


class HTTPLockedError(HTTPClientError):
    # pylint: disable=too-many-ancestors
    status_code = status.HTTP_423_LOCKED
