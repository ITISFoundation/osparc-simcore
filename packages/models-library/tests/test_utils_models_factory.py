# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Callable, Dict, Optional

from models_library.generics import Envelope
from models_library.rest_pagination import Page
from models_library.utils.models_factory import copy_model
from pydantic import BaseModel, validator
from pydantic.types import PositiveInt

# HELPERS -----


def copy_dict(obj: Dict, *, exclude={}):
    return {k: v for k, v in obj.items() if k not in exclude}


def update_dict(obj: Dict, **updates):
    for key, value in updates.items():
        if callable(value):
            value = value(obj[key])
        obj.update({key: value})
    return obj


def validators_factory() -> Callable:
    """Common validators"""

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

    _map = {
        "display_name": name_must_contain_space,
        "username": username_alphanumeric,
        "password2": passwords_match,
    }

    def _create(field_name) -> classmethod:
        return validator(field_name, allow_reuse=True)(_map[field_name])

    return _create


create_validator_for = validators_factory()


class User(BaseModel):
    """Domain model"""

    id: PositiveInt
    display_name: str
    username: str
    password: str

    # validators when model created in code
    _name_must_contain_space = create_validator_for("display_name")
    _username_alphanumeric = create_validator_for("username")


class UserCreate(BaseModel):
    """in -> Model for body of POST /users"""

    display_name: str
    username: str
    password: str
    password2: str

    # parses json-body from Create request
    _name_must_contain_space = create_validator_for("display_name")
    _username_alphanumeric = create_validator_for("username")
    _passwords_match = create_validator_for("password2")


class UserUpdate(BaseModel):
    """in -> Model for body of PATCH /users/{id}"""

    display_name: Optional[str]
    username: Optional[str]
    password: Optional[str]
    password2: Optional[str]

    # parses json-body from Update request
    _name_must_contain_space = create_validator_for("display_name")
    _username_alphanumeric = create_validator_for("username")
    _passwords_match = create_validator_for("password2")


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


# TESTS --------------------------------------------------------


def test_build_create_model():

    _BaseUserCreate = copy_model(User, name="_BaseUserCreate", exclude={"id"})

    class _UserCreate(_BaseUserCreate):
        """in -> Model for body of POST /users"""

        password2: str

        _passwords_match = create_validator_for("password2")

    # assert UserCreate.__fields__ == _UserCreate.__fields__
    # assert UserCreate.__get_validators__() == _UserCreate.__get_validators__()

    assert UserCreate.schema() == update_dict(
        _UserCreate.schema(), title=lambda v: v.lstrip("_")
    )


def test_build_update_model():
    pass


def test_build_replace_model():
    pass


def test_build_get_model():
    pass


def test_build_list_item_model():
    pass


def test_build_page_model():
    pass
