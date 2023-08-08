import functools
import inspect

from aiohttp import web
from aiohttp_security.api import check_authorized
from servicelib.aiohttp.typing_extension import HandlerAnyReturn
from servicelib.request_keys import RQT_USERID_KEY


def login_required(handler: HandlerAnyReturn) -> HandlerAnyReturn:
    """Decorator that restrict access only for authorized users

    - User is considered authorized if check_authorized(request) raises no exception
    - If authorized, it injects user_id in request[RQT_USERID_KEY]

    WARNING: Add always @router. decorator FIRST, e.g.

        @router.get("/foo")
        @login_required
        async def get_foo(request: web.Request):
            ...

    and NOT as

        @login_required
        @router.get("/foo")
        async def get_foo(request: web.Request):
            ...

    since the latter will register in `router` get_foo **without** `login_required`
    """
    assert set(inspect.signature(handler).parameters.values()) == {  # nosec
        inspect.Parameter(
            name="request",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=web.Request,
        )
    }, f"Expected {handler.__name__} with request as signature, got {handler.__annotations__}"

    @functools.wraps(handler)
    async def _wrapper(request: web.Request):
        # WARNING: note that check_authorized is patched in some tests.
        # Careful when changing the function signature
        request[RQT_USERID_KEY] = await check_authorized(request)
        return await handler(request)

    return _wrapper
