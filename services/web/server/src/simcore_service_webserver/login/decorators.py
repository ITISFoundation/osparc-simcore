from functools import wraps

from aiohttp import web
from aiohttp_security.api import check_authorized
from servicelib.aiohttp.typing_extension import Handler
from servicelib.request_keys import RQT_USERID_KEY


def _get_request(*args, **kwargs) -> web.BaseRequest:
    """Helper for handler function decorators to retrieve requests"""
    request = kwargs.get("request", args[-1] if args else None)
    if not isinstance(request, web.BaseRequest):
        msg = (
            "Incorrect decorator usage. "
            "Expecting `def handler(request)` "
            "or `def handler(self, request)`."
        )
        raise TypeError(msg)
    return request


def login_required(handler: Handler):
    """Decorator that restrict access only for authorized users.

    User is considered authorized if check_authorized(request) raises no exception

    Keeps userid in request[RQT_USERID_KEY]
    """

    @wraps(handler)
    async def wrapped(*args, **kwargs):
        request = _get_request(*args, **kwargs)
        # WARNING: note that check_authorized is patched in some tests.
        # Careful when changing the function signature
        request[RQT_USERID_KEY] = await check_authorized(request)
        return await handler(*args, **kwargs)

    return wrapped


__all__ = ("login_required",)
