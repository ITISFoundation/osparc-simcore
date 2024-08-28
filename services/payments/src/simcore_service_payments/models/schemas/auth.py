from typing import Literal

from pydantic.v1 import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
