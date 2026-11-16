from aiohttp import web
from aiohttp_security.api import IDENTITY_KEY, forget, remember
from models_library.emails import LowerCaseEmailStr

# Identification *string* for an authenticated user
type IdentityStr = str


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


async def get_identity(request: web.Request) -> IdentityStr | None:
    """Identify = Reads the verified identity stored in current session

    The stored value is the user's email (see remember_identity).
    aiohttp_security.api.authorized_userid cannot be used instead because the
    authorization policy maps the identity to the user id.
    """
    identity_policy = request.config_dict[IDENTITY_KEY]
    return await identity_policy.identify(request)
