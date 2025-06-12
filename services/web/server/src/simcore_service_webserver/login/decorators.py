import functools
import inspect
from typing import cast

from aiohttp import web
from models_library.users import UserID
from servicelib.aiohttp.typing_extension import HandlerAnyReturn
from servicelib.request_keys import RQT_USERID_KEY

from ..products import products_web
from ..security.api import (
    PERMISSION_PRODUCT_LOGIN_KEY,
    AuthContextDict,
    check_user_authorized,
    check_user_permission,
)


def login_required(handler: HandlerAnyReturn) -> HandlerAnyReturn:
    """Decorator that restrict access only for authorized users with permissions to access a given product

    - User is considered authorized if check_authorized(request) raises no exception
    - If authorized, it injects user_id in request[RQT_USERID_KEY]
    - Use this decorator instead of aiohttp_security.api.login_required!

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
        """
        Raises:
            HTTPUnauthorized: if unauthorized user
            HTTPForbidden: if user not allowed in product
        """
        # WARNING: note that check_authorized is patched in some tests.
        # Careful when changing the function signature
        user_id = await check_user_authorized(request)
        product_name = products_web.get_product_name(request)

        await check_user_permission(
            request,
            PERMISSION_PRODUCT_LOGIN_KEY,
            context=AuthContextDict(
                product_name=product_name,
                authorized_uid=user_id,
            ),
        )

        request[RQT_USERID_KEY] = user_id
        return await handler(request)

    return _wrapper


def get_user_id(request: web.Request) -> UserID:
    return cast(UserID, request[RQT_USERID_KEY])
