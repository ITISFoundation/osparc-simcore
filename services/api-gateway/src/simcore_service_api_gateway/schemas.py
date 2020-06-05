from typing import List

from pydantic import BaseModel  # pylint: disable=no-name-in-module


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """ application data encoded in the JWT """

    user_id: int
    scopes: List[str] = []


class User(BaseModel):
    name: str
    email: str = None
    # role: str = None


# DUMMY
class UserInDB(User):
    hashed_password: str
    disabled: bool = None
