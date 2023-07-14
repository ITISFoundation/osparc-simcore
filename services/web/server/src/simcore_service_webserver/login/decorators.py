import functools

from aiohttp import web
from aiohttp_security.api import check_authorized
from servicelib.aiohttp.typing_extension import Handler
from servicelib.request_keys import RQT_USERID_KEY


def login_required(handler: Handler) -> Handler:
    """Decorator that restrict access only for authorized users.

    - User is considered authorized if check_authorized(request) raises no exception
    - If authorized, it injects user_id in request[RQT_USERID_KEY]

    WARNING: Apply below @router.get(... ), e.g.

    @router.get("/foo")
    @login_required
    def get_foo(request: web.Request):
        ...


    and NOT as

    @login_required
    @router.get("/foo")
    def get_foo(request: web.Request):
        ...

    since the latter will register in `router` get_foo **without** the `login_required`
    """

    @functools.wraps(handler)
    async def _wrapper(request: web.Request) -> web.StreamResponse:
        assert isinstance(request, web.Request)  # nosec
        # WARNING: note that check_authorized is patched in some tests.
        # Careful when changing the function signature
        request[RQT_USERID_KEY] = await check_authorized(request)
        return await handler(request)

    return _wrapper
