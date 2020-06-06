from typing import List

from pydantic import BaseModel  # pylint: disable=no-name-in-module


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """ application data encoded in the JWT """

    user_id: int
    scopes: List[str] = []


# TODO: Replace by real user models
class User(BaseModel):
    name: str
    email: str = None
    # role: str = None


class UserInDB(User):
    class Config:
        orm_mode = True
