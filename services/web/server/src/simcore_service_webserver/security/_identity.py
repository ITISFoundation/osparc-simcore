from typing import TypeAlias

from aiohttp import web
from aiohttp_security.api import forget, remember
from models_library.emails import LowerCaseEmailStr

# Identification string for an autheticated user:
# FIXME:
#   Identity is a string that is shared between the browser and the server.
#   Therefore it is recommended that a random string such as a uuid or hash is used rather
#   than things like a database primary key, user login/email, etc.
#
# SEE https://aiohttp-security.readthedocs.io/en/latest/usage.html#authentication
IdentityStr: TypeAlias = LowerCaseEmailStr


async def remember_identity_in_session(
    request: web.Request, response: web.Response, *, user_email: IdentityStr
) -> web.Response:
    await remember(request=request, response=response, identity=user_email)
    return response


async def forget_identity_in_session(
    request: web.Request, response: web.Response
) -> web.Response:
    """Drops verified identity stored in current session"""
    await forget(request, response)
    return response
