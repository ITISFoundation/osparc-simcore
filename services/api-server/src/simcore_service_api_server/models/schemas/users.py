from pydantic import BaseModel

from ..domain.users import User


class UserInResponse(User):
    pass


class UserInUpdate(BaseModel):
    first_name: str
    last_name: str
