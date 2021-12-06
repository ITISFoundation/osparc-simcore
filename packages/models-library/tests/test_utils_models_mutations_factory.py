# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Dict, Optional

from models_library.generics import Envelope
from models_library.rest_pagination import Page
from models_library.utils.models_mutations_factory import (
    create_model_for_replace_as,
    create_model_for_update_as,
    extract_fields,
)
from pydantic import BaseModel, validator
from pydantic.types import PositiveInt

# HELPERS -----


def copy_dict(obj: Dict, *, exclude={}):
    return {k: v for k, v in obj.items() if k not in exclude}


def name_must_contain_space(v):
    if " " not in v:
        raise ValueError("must contain a space")
    return v.title()


def passwords_match(v, values, **kwargs):
    password_ref = values.get("password")
    if password_ref is None:
        raise ValueError("reference password missing")
    elif v != password_ref:
        raise ValueError("passwords do not match")
    return v


def username_alphanumeric(v):
    assert v.isalnum(), "must be alphanumeric"
    return v


class User(BaseModel):
    """Domain model"""

    id: PositiveInt
    display_name: str
    username: str
    password: str

    # validators when model created in code
    _name_must_contain_space = validator("display_name", allow_reuse=True)(
        name_must_contain_space
    )
    _username_alphanumeric = validator("username", allow_reuse=True)(
        username_alphanumeric
    )


class UserCreate(BaseModel):
    """in -> Model for body of POST /users"""

    display_name: str
    username: str
    password: str
    password2: str

    # parses json-body from Create request
    _name_must_contain_space = validator("display_name", allow_reuse=True)(
        name_must_contain_space
    )
    _username_alphanumeric = validator("username", allow_reuse=True)(
        username_alphanumeric
    )
    _passwords_match = validator("password2", allow_reuse=True)(passwords_match)


class UserUpdate(BaseModel):
    """in -> Model for body of PATCH /users/{id}"""

    display_name: Optional[str]
    username: Optional[str]
    password: Optional[str]
    password2: Optional[str]

    # parses json-body from Update request
    _name_must_contain_space = validator("display_name", allow_reuse=True)(
        name_must_contain_space
    )
    _username_alphanumeric = validator("username", allow_reuse=True)(
        username_alphanumeric
    )
    _passwords_match = validator("password2", allow_reuse=True)(passwords_match)


# Model for body of PUT /users/{id}
UserReplace = UserCreate


class UserGet(BaseModel):
    """<- out Detailed model for response in GET /users/{id}"""

    id: int
    display_name: str
    username: str

    # parses from User (i.e. validated domain model)


UserGetEnveloped = Envelope[UserGet]


class UserListItem(BaseModel):
    """<- out Item model for response in GET /users"""

    id: int
    username: str

    # parses from User


UsersList = Page[UserListItem]


# TESTS ----------------------


def test_mutations_factories():

    _UserCreate = create_model_for_replace_as(User, exclude={"id"})

    assert UserCreate == _UserCreate
