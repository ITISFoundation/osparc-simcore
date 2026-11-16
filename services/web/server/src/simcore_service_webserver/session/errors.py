from aiohttp import web

from ..errors import WebServerBaseError


class SessionValueError(WebServerBaseError, ValueError):
    msg_template = "Invalid {invalid} in session"


class HTTPRefundableTooManyRequests(web.HTTPTooManyRequests):  # pylint: disable=too-many-ancestors
    """429 raised from inside a session_access_required-guarded handler

    The guard refunds the access this request consumed, so waiting for
    Retry-After and retrying does not run the session out of authorization.
    Only this error refunds: any other 429 (e.g. route rate limiting, which
    runs outside the guard) keeps its cost.
    """
