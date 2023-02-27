from functools import wraps

from aiohttp_security.api import check_authorized
from servicelib.aiohttp.requests_utils import get_request
from servicelib.request_keys import RQT_USERID_KEY


def login_required(handler):
    """Decorator that restrict access only for authorized users.

    User is considered authorized if check_authorized(request) raises no exception

    Keeps userid in request[RQT_USERID_KEY]
    """

    @wraps(handler)
    async def wrapped(*args, **kwargs):
        request = get_request(*args, **kwargs)
        # WARNING: not that check_authorized is patched in some tests.
        # Careful when changing the function signature
        request[RQT_USERID_KEY] = await check_authorized(request)
        ret = await handler(*args, **kwargs)
        return ret

    return wrapped


__all__ = ("login_required",)
