from aiohttp.web_exceptions import HTTPClientError


class HTTPLockedError(HTTPClientError):
    # pylint: disable=too-many-ancestors
    status_code = 423
