# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Dict, Optional

from models_library.utils.models_mutations_factory import extract_fields
from pydantic import BaseModel, Field, create_model


def copy_dict(obj: Dict, *, exclude={}):
    return {k: v for k, v in obj.items() if k not in exclude}


class User(BaseModel):
    user_id: int = Field(...)
    username: Optional[str] = "Anonymous"
    password: Optional[str]


def test_create_reduced_model():
    class UserOut_expected(BaseModel):
        user_id: int = Field(...)
        username: Optional[str] = "Anonymous"
        password: Optional[str]

    print(UserOut_expected.schema_json(indent=1))

    UserOut = create_model("UserOut", **extract_fields(User, exclude={"password"}))
    print(UserOut.schema_json(indent=1))

    assert not issubclass(UserOut, BaseModel)

    assert copy_dict(UserOut.schema(), exclude={"title"}) == copy_dict(
        UserOut.schema(), exclude={"title"}
    )
    assert not issubclass(UserOut, User)


# UserOut = create_model_for_replace_as(User, exclude={"password"})
# class UserOut(User):
#     password: str = Field(..., exclude=True)


# class UserInCreate(User):
#     user_id: str = Field(..., exclude=True)  # this is decided on the server-side
#     repeat_password: str = Field(...)


# UserInUpdate = create_model_for_update_as(UserInCreate, exclude=None)


# class UserInUpdate(User):
#     username: Optional[str]
#     password: Optional[str]
#     repeat_password: str = Field(...)


# print(UserOut.__fields__)
