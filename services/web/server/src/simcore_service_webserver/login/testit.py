from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field, root_validator


class RegisterBody(BaseModel):
    email: LowerCaseEmailStr
    user: str = Field(None, description="User name", hidden=True)

    @root_validator(pre=True)
    @classmethod
    def _validate_user(cls, values):
        values["user"] = values["email"].split("@")[0]
        return values


data = RegisterBody(email="aHoJ@gmail.com")
print(data)
