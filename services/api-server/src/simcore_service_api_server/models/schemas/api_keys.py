from pydantic import BaseModel

from ..domain.api_keys import ApiKey


class ApiKeyInLogin(ApiKey):
    pass


class ApiKeyInResponse(BaseModel):
    display_name: str
    token: str
