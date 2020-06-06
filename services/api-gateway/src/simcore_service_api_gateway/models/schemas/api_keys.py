from ..domain.api_keys import ApiKey
from pydantic import BaseModel


class ApiKeyInLogin(ApiKey):
    pass


class ApiKeyInResponse(BaseModel):
    display_name: str
    token: str
