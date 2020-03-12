import asyncio
from functools import wraps

from aiohttp import web
from aiohttp_security.api import authorized_userid

from servicelib.request_keys import RQT_USERID_KEY
from servicelib.requests_utils import get_request


@asyncio.coroutine
def user_to_request(handler):
    """ Handler decorator that injects in request, current authorized user ID

    """

    @wraps(handler)
    async def wrapped(*args, **kwargs):
        request = get_request(*args, **kwargs)
        request[RQT_USERID_KEY] = await authorized_userid(request)
        return await handler(*args)

    return wrapped


def login_required(handler):
    """Decorator that restrict access only for authorized users.

    User is considered authorized if authorized_userid
    returns some value.

    Keeps userid in request[RQT_USERID_KEY]
    """

    @wraps(handler)
    async def wrapped(*args, **kwargs):
        request = get_request(*args, **kwargs)
        userid = await authorized_userid(request)
        if userid is None:
            raise web.HTTPUnauthorized

        request[RQT_USERID_KEY] = userid
        ret = await handler(*args, **kwargs)
        return ret

    return wrapped


__all__ = "login_required"
