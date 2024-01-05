from typing import TypeAlias

from aiohttp import web
from aiohttp_security.api import forget, remember
from models_library.emails import LowerCaseEmailStr

# Identification string for an autheticated user
IdentityStr: TypeAlias = LowerCaseEmailStr


async def remember_identity(
    request: web.Request, response: web.Response, *, user_email: IdentityStr
) -> web.Response:
    await remember(request=request, response=response, identity=user_email)
    return response


# Drops identity in current session
forget_identity = forget
