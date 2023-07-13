import functools

from aiohttp import web
from aiohttp_security.api import check_authorized
from servicelib.aiohttp.typing_extension import Handler
from servicelib.request_keys import RQT_USERID_KEY


def login_required(handler: Handler):
    """Decorator that restrict access only for authorized users.

    User is considered authorized if check_authorized(request) raises no exception

    Keeps userid in request[RQT_USERID_KEY]
    """

    @functools.wraps(handler)
    async def wrapped(request: web.Request):
        assert isinstance(request, web.Request)  # nosec
        # WARNING: note that check_authorized is patched in some tests.
        # Careful when changing the function signature
        request[RQT_USERID_KEY] = await check_authorized(request)
        return await handler(request)

    return wrapped
