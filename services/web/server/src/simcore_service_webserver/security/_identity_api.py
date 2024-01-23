from typing import TypeAlias

import ujson
from aiohttp import web
from aiohttp_security.api import forget, remember
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from pydantic import BaseModel, Extra, Field

# Identification *string* for an autheticated user
IdentityStr: TypeAlias = str


class IdentityModel(BaseModel):
    email: LowerCaseEmailStr = Field(alias="e")
    product_name: ProductName = Field(alias="p")

    class Config:
        anystr_strip_whitespace = True
        extra = Extra.forbid
        json_loads = ujson.loads
        json_dumps = ujson.dumps

    @classmethod
    def create(cls, identity: IdentityStr) -> "IdentityModel":
        return cls.parse_raw(identity)

    def to_identity(self) -> IdentityStr:
        return self.json(by_alias=True)


async def remember_identity(
    request: web.Request,
    response: web.Response,
    *,
    user_email: LowerCaseEmailStr,
    product_name: ProductName
) -> web.Response:
    """Remember = Saves verified identify in current session"""
    verified = IdentityModel(e=user_email, p=product_name)
    await remember(
        request=request,
        response=response,
        identity=verified.to_identity(),
    )
    return response


async def forget_identity(request: web.Request, response: web.Response) -> web.Response:
    """Forget = Drops verified identity stored in current session"""
    await forget(request, response)
    return response
