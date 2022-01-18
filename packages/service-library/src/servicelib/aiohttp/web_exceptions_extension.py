from aiohttp.web_exceptions import HTTPClientError


class HTTPLocked(HTTPClientError):
    # pylint: disable=too-many-ancestors
    status_code = 423
