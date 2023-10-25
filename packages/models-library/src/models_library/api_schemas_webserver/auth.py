from models_library.emails import LowerCaseEmailStr
from pydantic import SecretStr

from ._base import InputSchema


class UnregisterCheck(InputSchema):
    email: LowerCaseEmailStr
    password: SecretStr
