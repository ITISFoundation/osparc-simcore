from typing import TypeAlias

from aiohttp import web
from aiohttp_security.api import forget, remember  # type: ignore[import-untyped]
from models_library.emails import LowerCaseEmailStr

# Identification *string* for an autheticated user
IdentityStr: TypeAlias = str


async def remember_identity(
    request: web.Request,
    response: web.Response,
    *,
    user_email: LowerCaseEmailStr,
) -> web.Response:
    """Remember = Saves verified identify in current session"""
    await remember(
        request=request,
        response=response,
        identity=user_email,
    )
    return response


async def forget_identity(request: web.Request, response: web.Response) -> web.Response:
    """Forget = Drops verified identity stored in current session"""
    await forget(request, response)
    return response
