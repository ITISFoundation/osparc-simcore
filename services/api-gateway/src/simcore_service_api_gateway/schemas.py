from typing import List

from pydantic import BaseModel  # pylint: disable=no-name-in-module


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str = None
    scopes: List[str] = []


class User(BaseModel):
    username: str
    email: str = None
    full_name: str = None

class UserInDB(User):
    hashed_password: str
    disabled: bool = None
