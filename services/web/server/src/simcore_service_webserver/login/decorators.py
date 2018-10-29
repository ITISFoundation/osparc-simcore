import asyncio
from functools import wraps

from aiohttp import web
from aiohttp_security.api import authorized_userid, permits

from servicelib.request_keys import RQT_USERID_KEY
from servicelib.requests_utils import get_request

from ..db_models import UserRole


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
    @user_to_request
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        request = get_request(*args, **kwargs)
        userid = request[RQT_USERID_KEY]
        if userid is None:
            raise web.HTTPUnauthorized

        ret = await handler(*args, **kwargs)
        return ret
    return wrapped


def restricted_to(
    permission: UserRole,
    context=None,
):
    """Decorator that restrict access only for authorized users
    with a minimum role.

    If user is not authorized - raises HTTPUnauthorized,
    If user is authorized and does not have permission -
    raises HTTPForbidden.

    Keeps userid in request[RQT_USERID_KEY]
    """
    def wrapper(handler):
        @user_to_request
        @wraps(handler)
        def wrapped(*args, **kwargs):
            request = get_request(*args, **kwargs)
            userid = request[RQT_USERID_KEY]
            if userid is None:
                raise web.HTTPUnauthorized

            allowed = yield from permits(request, permission, context)
            if not allowed:
                raise web.HTTPForbidden
            ret = yield from handler(*args, **kwargs)
            return ret

        return wrapped

    return wrapper


__all__ = (
    "login_required",
    "restricted_to"
)
