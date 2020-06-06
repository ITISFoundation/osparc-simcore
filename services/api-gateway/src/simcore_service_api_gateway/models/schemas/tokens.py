from typing import List

from pydantic import BaseModel
from datetime import datetime


class JWTMeta(BaseModel):
    exp: datetime
    sub: str


class JWTUser(BaseModel):
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """ application data encoded in the JWT """
    user_id: int
    scopes: List[str] = []
