from aiohttp.web import RouteTableDef
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field, PositiveInt, SecretStr

from ....utils_aiohttp import NextPage
from ..._models import InputSchema

routes = RouteTableDef()


class LoginBody(InputSchema):
    email: LowerCaseEmailStr
    password: SecretStr


class CodePageParams(BaseModel):
    message: str
    expiration_2fa: PositiveInt | None = None
    next_url: str | None = None


class LoginNextPage(NextPage[CodePageParams]): ...


class LoginTwoFactorAuthBody(InputSchema):
    email: LowerCaseEmailStr
    code: SecretStr


class LogoutBody(InputSchema):
    client_session_id: str | None = Field(
        None, examples=["5ac57685-c40f-448f-8711-70be1936fd63"]
    )
