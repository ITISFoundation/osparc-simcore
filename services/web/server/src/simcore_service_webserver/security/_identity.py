from typing import TypeAlias

from aiohttp import web
from aiohttp_security.api import forget, remember
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from pydantic import BaseModel

IdentityJsonStr: TypeAlias = str


class VerifiedIdentity(BaseModel):
    """
    identity = await identity_policy.identify(request)
    if identity is None:
        return None  # non-registered user has None user_id
    user_id = await autz_policy.authorized_userid(identity)
    return user_id
    """

    product_name: ProductName
    email: LowerCaseEmailStr


async def remember_identity(
    request: web.Request, response: web.Response, verified_user: VerifiedIdentity
) -> web.Response:
    identity: IdentityJsonStr = verified_user.json()
    await remember(request=request, response=response, identity=identity)
    return response


forget_identity = forget
